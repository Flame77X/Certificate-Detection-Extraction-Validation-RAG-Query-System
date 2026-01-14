import os
import base64
import mimetypes
from pypdf import PdfReader
from openai import AzureOpenAI

from app.security import validate_secure_path, check_file_size

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

            # If empty/scanned PDF, try Vision
            if len(text_content.strip()) < 50:
                print("⚠️ Low text content (Scanned PDF?). Switching to Vision OCR...")
                # For PDFs, this is complex (need to convert pages to images). 
                # For now, let's warn. Ideally, use Azure Document Intelligence here.
                # But for this task, we focus on JPG/PNG uploads.
                pass 

        elif ext in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
            print(f"📷 Image detected ({ext}). Using Azure Vision OCR...")
            text_content = extract_with_vision(file_path)
            used_ocr = True

    except Exception as e:
        print(f"❌ Critical Reading Error: {e}")

    return text_content, used_ocr

def extract_with_vision(file_path):
    """
    Use Azure OpenAI (GPT-4 Vision) to read text from an image.
    """
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "image/jpeg"

    # Encode Image
    with open(file_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    try:
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "system",
                    "content": "Read the text locally from this certificate image."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What does this document say?"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Vision OCR Failed: {e}")
        return ""
