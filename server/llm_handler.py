import os
import base64
import io
from openai import OpenAI
from dotenv import load_dotenv
import fitz  # PyMuPDF
from PIL import Image

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# gpt-4o: best multimodal model for structured extraction from engineering drawings.
# "detail: high" tiles each page into 512px patches — critical for reading fine
# reinforcement schedules and dimension annotations on structural drawings.
VISION_MODEL = "gpt-4o"


# OpenAI silently drops images larger than ~20 MB.
# At 200 DPI an A1 drawing renders to ~6600×4700 px (~30 MB PNG) — always dropped.
# 150 DPI + 2048-px cap keeps every page well under 5 MB while still being sharp
# enough to read reinforcement schedules and dimension annotations.
_MAX_DIM = 2048


def pdf_to_images(pdf_source):
    """Convert each page of a PDF to PIL Images, capped at 2048 px.

    Args:
        pdf_source: file path (str) or raw PDF bytes.
    """
    images = []
    try:
        if isinstance(pdf_source, (bytes, bytearray)):
            doc = fitz.open(stream=pdf_source, filetype="pdf")
        else:
            doc = fitz.open(pdf_source)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            # Resize so the longest side is at most _MAX_DIM pixels.
            w, h = img.size
            if max(w, h) > _MAX_DIM:
                scale = _MAX_DIM / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            images.append(img)
        doc.close()
    except Exception as e:
        print(f"Error processing PDF: {e}")
        raise
    return images


def pil_to_base64(image: Image.Image) -> str:
    """Encode a PIL Image to a base64 PNG string."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def run_specialist_agent(images: list, drawing_type: str) -> str:
    """Route drawing images to the correct specialist prompt and call gpt-4o.

    Args:
        images: List of PIL Image objects (one per PDF page).
        drawing_type: "foundation" | "slab" | "beam" | "column" | "unknown".

    Returns:
        Initial compliance report as a Markdown string.
    """
    from prompt import PROMPT_REGISTRY, INITIAL_EXTRACTION_PROMPT

    prompt = PROMPT_REGISTRY.get(drawing_type, INITIAL_EXTRACTION_PROMPT)
    if drawing_type == "unknown":
        print("⚠ Unknown drawing type — falling back to foundation prompt.")

    print(f"🏗 Specialist agent running for: {drawing_type}")

    image_content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{pil_to_base64(img)}",
                "detail": "high",   # tile-based: reads fine annotations
            },
        }
        for img in images
    ]

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                # System message: prevents the "I'm unable to analyze images" preamble
                # that gpt-4o sometimes emits when it hasn't processed image tokens yet.
                "role": "system",
                "content": (
                    "You are a Senior Indian Civil Engineer and RCC drawing compliance expert. "
                    "Structural drawing images are attached to this message and ARE fully visible to you. "
                    "You MUST analyze them directly. "
                    "NEVER say you cannot view or analyze images. "
                    "Begin your response IMMEDIATELY with '### Step 0: Initial Document Check' — "
                    "no preamble, no disclaimers, no capability statements."
                ),
            },
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}] + image_content,
            },
        ],
        temperature=0,
        max_tokens=4096,
    )

    return response.choices[0].message.content
