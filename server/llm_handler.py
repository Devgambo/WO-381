import os
import base64
import io
from openai import OpenAI, APIError
from dotenv import load_dotenv
import fitz  # PyMuPDF
from PIL import Image

# Load environment variables from .env file
load_dotenv()

def pdf_to_images(pdf_path):
    """Converts each page of a PDF into a list of PIL Image objects."""
    images = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Higher DPI for better quality
            pix = page.get_pixmap(dpi=200)
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            images.append(image)
        doc.close()
    except Exception as e:
        print(f"Error processing PDF file: {e}")
        raise
    return images

def pil_to_base64(image):
    """Converts a PIL Image to a base64 encoded string."""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def analyze_rcc_drawing_from_images(images, prompt_text):
    """
    Analyzes RCC drawing images directly using the OpenRouter API.

    Args:
        images (list): List of PIL Image objects to analyze.
        prompt_text (str): The text prompt to guide the analysis.

    Returns:
        str: The generated text response from the model.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in .env file.")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    try:
        print(f"Processing {len(images)} image(s)...")
        base64_images = [pil_to_base64(img) for img in images]

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                ] + [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img}"
                        }
                    } for img in base64_images
                ]
            }
        ]

        print("Sending request to OpenRouter...")
        response = client.chat.completions.create(
            model="google/gemini-2.5-flash",
            messages=messages,
            max_tokens=4000,
            temperature=0,
        )
        print("Received response from OpenRouter.")
        
        return response.choices[0].message.content

    except APIError as e:
        error_msg = str(e)
        error_code = getattr(e, 'status_code', None) or getattr(e, 'code', None)
        print(f"OpenRouter API error: {error_msg}")
        
        # Handle specific error codes
        if error_code == 402 or "402" in error_msg or "Insufficient credits" in error_msg:
            raise ValueError(
                "❌ OpenRouter API Error: Insufficient credits.\n\n"
                "Your OpenRouter account does not have sufficient credits to make this request.\n\n"
                "To fix this:\n"
                "1. Visit https://openrouter.ai/settings/credits\n"
                "2. Purchase credits for your account\n"
                "3. Ensure your API key is correct and associated with the account that has credits\n\n"
                f"Technical details: {error_msg}"
            ) from e
        elif error_code == 401 or "401" in error_msg or "Unauthorized" in error_msg:
            raise ValueError(
                "❌ OpenRouter API Error: Invalid API key.\n\n"
                "Your OPENROUTER_API_KEY is invalid or expired.\n\n"
                "To fix this:\n"
                "1. Visit https://openrouter.ai/keys\n"
                "2. Create a new API key\n"
                "3. Update your .env file with the new key\n\n"
                f"Technical details: {error_msg}"
            ) from e
        else:
            raise ValueError(
                f"❌ OpenRouter API Error: {error_msg}\n\n"
                "Please check your API key and account status at https://openrouter.ai/"
            ) from e
    except Exception as e:
        error_msg = str(e)
        print(f"An error occurred during the analysis: {error_msg}")
        raise ValueError(f"❌ Error analyzing images: {error_msg}") from e

def analyze_rcc_drawing(pdf_path, prompt_text):
    """
    Analyzes an RCC drawing PDF using the OpenRouter API.

    Args:
        pdf_path (str): The path to the PDF file.
        prompt_text (str): The text prompt to guide the analysis.

    Returns:
        str: The generated text response from the model.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in .env file.")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    try:
        print(f"Converting PDF '{pdf_path}' to images...")
        images = pdf_to_images(pdf_path)
        print(f"Successfully converted {len(images)} pages to images.")

        # Use the shared function for image analysis
        return analyze_rcc_drawing_from_images(images, prompt_text)

    except ValueError as e:
        # Re-raise ValueError (from analyze_rcc_drawing_from_images) as-is
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"An error occurred during the analysis: {error_msg}")
        raise ValueError(f"❌ Error analyzing PDF: {error_msg}") from e

def run_specialist_agent(images, drawing_type: str) -> str:
    """
    Route images to the correct specialist agent based on drawing type.

    Maps the drawing_type to the appropriate prompt from PROMPT_REGISTRY
    and calls analyze_rcc_drawing_from_images.

    Args:
        images: List of PIL Image objects.
        drawing_type: One of "foundation", "slab", "beam", or "unknown".

    Returns:
        str: The generated initial report markdown.
    """
    from prompt import PROMPT_REGISTRY, INITIAL_EXTRACTION_PROMPT

    prompt = PROMPT_REGISTRY.get(drawing_type, INITIAL_EXTRACTION_PROMPT)

    if drawing_type == "unknown":
        print("⚠ Unknown drawing type — falling back to foundation prompt.")

    print(f"🏗 Running specialist agent for: {drawing_type}")
    return analyze_rcc_drawing_from_images(images, prompt)