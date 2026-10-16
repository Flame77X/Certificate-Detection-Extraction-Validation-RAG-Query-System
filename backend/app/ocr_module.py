import os
import base64
import mimetypes
from pypdf import PdfReader

from app.security import validate_secure_path, check_file_size
from app.llm_client import get_client, chat_deployment

# Below this many characters a PDF is treated as scanned (image-only)
MIN_PDF_TEXT_CHARS = 50
# Cap vision calls per scanned PDF (cost / latency)
MAX_SCANNED_PAGES = 3

VISION_PROMPT = (
    "Transcribe all text visible in this certificate image exactly as printed, "
    "line by line, including names, IDs and dates. Do not summarise, translate or add commentary. "
    "If no text is legible, return an empty response."
)

def extract_text_from_file(file_path):
    """
    Extract text from a file.
    Strategies:
    1. Direct Text Read (TXT)
    2. Digital PDF Extraction (PyPDF)
    3. Vision OCR (Azure GPT-4) - For images & scanned PDFs
    """
    # --- SECURITY CHECKS ---
    safe_path = validate_secure_path(file_path)
    check_file_size(safe_path)
    # -----------------------
    
    file_path = safe_path
    ext = file_path.split('.')[-1].lower()
    text_content = ""
    used_ocr = False

    try:
        if ext == 'txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
        
        elif ext == 'pdf':
            # Strategy 1: PyPDF
            try:
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text_content += (page.extract_text() or "") + "\n"
            except Exception as e:
                print(f"⚠️ PyPDF Read Error: {e}")

            # If empty/scanned PDF, OCR the page images embedded in the PDF
            if len(text_content.strip()) < MIN_PDF_TEXT_CHARS:
                print("⚠️ Low text content (Scanned PDF?). Switching to Vision OCR...")
                scanned_text = extract_scanned_pdf(file_path)
                if scanned_text.strip():
                    text_content = scanned_text
                    used_ocr = True

        elif ext in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
            print(f"📷 Image detected ({ext}). Using Azure Vision OCR...")
            text_content = extract_with_vision(file_path)
            used_ocr = True

    except Exception as e:
        print(f"❌ Critical Reading Error: {e}")

    return text_content, used_ocr

def extract_scanned_pdf(file_path):
    """
    OCR a scanned PDF by sending each page's embedded image(s) to the vision model.
    Scanners typically store one full-page image per page, so no PDF rasteriser is needed.
    """
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        print(f"⚠️ PyPDF Read Error: {e}")
        return ""

    page_texts = []
    for page in reader.pages[:MAX_SCANNED_PAGES]:
        try:
            images = list(page.images)
        except Exception as e:
            print(f"⚠️ Could not decode page images: {e}")
            continue
        for image in images:
            mime_type, _ = mimetypes.guess_type(image.name)
            text = _vision_ocr(image.data, mime_type or "image/png")
            if text:
                page_texts.append(text)
    return "\n".join(page_texts)

def extract_with_vision(file_path):
    """
    Use Azure OpenAI (GPT-4 Vision) to read text from an image file.
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    with open(file_path, "rb") as image_file:
        return _vision_ocr(image_file.read(), mime_type or "image/jpeg")

def _vision_ocr(image_bytes, mime_type):
    """Send raw image bytes to the vision model and return the transcribed text."""
    client = get_client()
    if not client:
        print("⚠️ Vision OCR skipped: Azure OpenAI is not configured.")
        return ""
    
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    try:
        response = client.chat.completions.create(
            model=chat_deployment(),
            messages=[
                {
                    "role": "system",
                    "content": "You are an OCR engine. Output only the transcribed text."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"❌ Vision OCR Failed: {e}")
        return ""
