import base64
import io
import logging
import os

import fitz  # PyMuPDF
from PIL import Image

from openai_client import VISION_MODEL, get_openai_client

log = logging.getLogger(__name__)

# OpenAI silently drops images larger than ~20 MB.
# At 200 DPI an A1 drawing renders to ~6600×4700 px (~30 MB PNG) — always dropped.
# Cap so each page lands well under 5 MB while keeping fine reinforcement
# annotations readable.
_MAX_DIM = 3072
_RENDER_DPI = 220
_MAX_PAGES_PER_PDF = int(os.getenv("MAX_PAGES_PER_PDF", "30"))


class PdfTooLargeError(ValueError):
    """Raised when a PDF exceeds MAX_PAGES_PER_PDF."""


def pdf_to_images(pdf_source, max_pages: int | None = None) -> list[Image.Image]:
    """Convert each PDF page to a PIL Image, longest side capped at _MAX_DIM."""
    images: list[Image.Image] = []
    if isinstance(pdf_source, (bytes, bytearray)):
        doc = fitz.open(stream=pdf_source, filetype="pdf")
    else:
        doc = fitz.open(pdf_source)
    try:
        limit = max_pages if max_pages is not None else _MAX_PAGES_PER_PDF
        if doc.page_count > limit:
            raise PdfTooLargeError(
                f"PDF has {doc.page_count} pages; per-document limit is {limit}."
            )
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=_RENDER_DPI)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            w, h = img.size
            if max(w, h) > _MAX_DIM:
                scale = _MAX_DIM / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            size_mb = len(buf.getvalue()) / (1024 * 1024)
            if size_mb > 18:
                log.warning(
                    "PDF page %d rendered to %.1f MB — approaching OpenAI cap. "
                    "Consider lowering _RENDER_DPI.",
                    page_num + 1, size_mb,
                )
            images.append(img)
    finally:
        doc.close()
    return images


def pil_to_base64(image: Image.Image) -> str:
    """Encode a PIL Image to a base64 PNG string."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def run_specialist_agent(base64_images: list[str], drawing_type: str) -> str:
    """Route base64 drawing images to the correct specialist prompt and call the vision model.

    Args:
        base64_images: pre-encoded PNG base64 strings (one per page).
        drawing_type: "foundation" | "slab" | "beam" | "column" | "unknown".

    Returns:
        Initial compliance report as a Markdown string.
    """
    from prompt import INITIAL_EXTRACTION_PROMPT, PROMPT_REGISTRY

    prompt = PROMPT_REGISTRY.get(drawing_type, INITIAL_EXTRACTION_PROMPT)
    if drawing_type == "unknown":
        log.warning("Unknown drawing type — falling back to foundation prompt.")

    log.info("Specialist agent running for: %s", drawing_type)

    image_content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{img}",
                "detail": "high",  # tile-based: reads fine annotations
            },
        }
        for img in base64_images
    ]

    response = get_openai_client().chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a Senior Indian Civil Engineer and RCC drawing compliance expert. "
                    "Structural drawing images are attached to this message and ARE fully visible to you. "
                    "You MUST analyze them directly. "
                    "NEVER say you cannot view or analyze images. "
                    "Begin your response IMMEDIATELY with '### Phase 1' — "
                    "no preamble, no disclaimers, no capability statements."
                ),
            },
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}] + image_content,
            },
        ],
        temperature=0,
        max_tokens=16000,
    )

    choice = response.choices[0]
    content = choice.message.content
    if not content or not content.strip():
        # N3: empty vision-model output → splitlines crash downstream.
        finish = getattr(choice, "finish_reason", "?")
        raise ValueError(
            f"Vision model returned no content (finish_reason={finish}). "
            "Likely model output blocked or truncated — please retry."
        )
    return content
