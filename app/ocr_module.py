import os
from pypdf import PdfReader

# Optional: Import Azure DI libraries if verified in future
# from azure.ai.documentintelligence import DocumentIntelligenceClient
# from azure.core.credentials import AzureKeyCredential

def extract_text_from_file(file_path):
    """
    Extract text from a file.
    Strategies:
    1. Direct Text Read (TXT)
    2. Digital PDF Extraction (PyPDF)
    3. OCR Extraction (Azure Document Intelligence) - Falback
    """
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
                    text = page.extract_text()
                    if text:
                        text_content += text + "\n"
            except Exception as e:
                print(f"⚠️ PyPDF Read Error: {e}")

            # Detection of Scanned PDF
            # If text is extremely short or empty, it's likely an image
            if len(text_content.strip()) < 50:
                print("⚠️ Low text content detected. Likely a SCANNED document.")
                print("🔄 Attempting OCR (Document Intelligence)...")
                
                # Strategy 2: OCR (Stubbed for now)
                ocr_text = try_azure_ocr(file_path)
                if ocr_text:
                    text_content = ocr_text
                    used_ocr = True
                else:
                    print("❌ OCR Failed: No Document Intelligence keys configured.")
                    print("   (To fix: Add AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and KEY to .env)")

    except Exception as e:
        print(f"❌ Critical Reading Error: {e}")

    return text_content, used_ocr

def try_azure_ocr(file_path):
    """
    Attempt to use Azure Document Intelligence if keys are present.
    Returns text string or None.
    """
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

    if not endpoint or not key:
        return None

    try:
        # Placeholder for actual implementation code in future
        # client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))
        # with open(file_path, "rb") as f:
        #     poller = client.begin_analyze_document("prebuilt-read", document=f)
        # result = poller.result()
        # return result.content
        return None
    except Exception:
        return None
