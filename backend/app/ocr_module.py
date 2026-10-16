import os
import base64
import mimetypes
from pypdf import PdfReader

from app.security import validate_secure_path, check_file_size
from app.llm_client import get_client, chat_deployment, is_configured

# Below this many characters a PDF is treated as scanned (image-only)
MIN_PDF_TEXT_CHARS = 50
# Cap vision calls per scanned PDF (cost / latency)
MAX_SCANNED_PAGES = 3

# OCR engine: 'azure' (GPT vision), 'local' (RapidOCR, free/offline), 'auto' (azure if configured, else local)
OCR_PROVIDERS = ('auto', 'azure', 'local')
# Lines RapidOCR scores below this are dropped as noise
LOCAL_OCR_MIN_SCORE = 0.5

_local_engine = None

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
    3. Image OCR (Azure GPT vision or local RapidOCR, see OCR_PROVIDER) - For images & scanned PDFs
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
                print("⚠️ Low text content (Scanned PDF?). Switching to image OCR...")
                scanned_text = extract_scanned_pdf(file_path)
                if scanned_text.strip():
                    text_content = scanned_text
                    used_ocr = True

        elif ext in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
            print(f"📷 Image detected ({ext}). Running OCR...")
            mime_type, _ = mimetypes.guess_type(file_path)
            with open(file_path, "rb") as image_file:
                text_content = ocr_image(image_file.read(), mime_type or "image/jpeg")
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
            text = ocr_image(image.data, mime_type or "image/png")
            if text:
                page_texts.append(text)
    return "\n".join(page_texts)

def _ocr_provider():
    provider = os.getenv("OCR_PROVIDER", "auto").lower()
    return provider if provider in OCR_PROVIDERS else "auto"

def ocr_image(image_bytes, mime_type):
    """Route image OCR to the configured engine. In 'auto', fall back to local OCR if Azure returns nothing."""
    provider = _ocr_provider()
    if provider == "local" or (provider == "auto" and not is_configured()):
        return _local_ocr(image_bytes)
    text = _vision_ocr(image_bytes, mime_type)
    if not text.strip() and provider == "auto":
        print("ℹ️  Azure vision returned no text; trying local OCR.")
        return _local_ocr(image_bytes)
    return text

def _local_ocr(image_bytes):
    """Free, offline OCR with RapidOCR (PaddleOCR models on ONNX Runtime, CPU)."""
    global _local_engine
    try:
        if _local_engine is None:
            from rapidocr import RapidOCR  # lazy: model load takes ~1s
            _local_engine = RapidOCR(params={"Global.log_level": "error"})
        result = _local_engine(image_bytes)
    except ImportError:
        print("❌ Local OCR unavailable: pip install rapidocr onnxruntime")
        return ""
    except Exception as e:
        print(f"❌ Local OCR Failed: {e}")
        return ""

    if not result.txts:
        return ""
    return "\n".join(t for t, s in zip(result.txts, result.scores) if s >= LOCAL_OCR_MIN_SCORE)

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
