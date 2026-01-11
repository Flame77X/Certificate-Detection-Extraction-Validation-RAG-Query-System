import sys
import os
import json
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.certificate_identification import is_certificate
from app.field_extraction import extract_with_azure, extract_fields, create_json_output
from app.date_validation import validate_dates
from app.logging_utils import log_extraction, check_for_issues
from app.ocr_module import extract_text_from_file

def main():
    parser = argparse.ArgumentParser(description="Certificate Extraction & Validation System (Part A)")
    parser.add_argument("--file", help="Path to the certificate file", default="sample_certificate.pdf")
    args = parser.parse_args()
    
    file_path = args.file
    
    # 1. Identify Certificate
    print(f"--- Processing: {file_path} ---")
    
    text_content = ""
    file_ext = "unknown"

    if os.path.exists(file_path):
        file_ext = os.path.splitext(file_path)[1].replace('.', '').lower()
        
        # Use centralized extraction (supports OCR fallback)
        text_content, used_ocr = extract_text_from_file(file_path)
        
        if used_ocr:
            print("ℹ️  Used OCR for text extraction.")

    # Fallback for demo if no file or empty text
    if not text_content.strip():
        if os.path.exists(file_path):
             print("⚠️  Could not extract text from file (maybe image-based PDF?). using fallback text.")
        else:
             print(f"⚠️  File {file_path} not found. Using MOCK text for demo.")
        
        text_content = """
        CERTIFICATE OF COMPLETION
        This is to certify that John Doe has completed the Quality Management System course.
        Certificate Number: ISO-9001-2024-098
        Issued By: ISO Authority
        Issued On: 2024-01-15
        Valid Until: 2026-01-15
        """
        file_ext = "pdf" if file_ext == "unknown" else file_ext

    print(f"📄 Extracted Text Length: {len(text_content)} chars")
    
    is_valid_cert = is_certificate(file_ext, text_content)
    
    if not is_valid_cert:
        print("❌ Document is NOT classified as a certificate.")
        print("   Reason: File type or Keywords missing.")
        print(f"   Snippet: {text_content[:500]}...")
        print("   (If this is a scanned PDF, the text cannot be read without OCR keys.)")
        return

    print("✅ Document identified as a certificate.")

    # 2. Extract Fields (Azure OpenAI)
    print("⏳ Extracting fields using Azure OpenAI...")
    raw_extraction = extract_with_azure(text_content)
    
    fields, confidence = extract_fields(raw_extraction)
    print("✅ Extraction complete.")

    # 3. Validate Dates
    print("⏳ Validating dates...")
    validation_result = validate_dates(fields.get('issued_date'), fields.get('expiry_date'))
    
    if validation_result['dates_consistent'] and validation_result['expiry_status'] == 'valid':
        print("✅ Date validation passed.")
    else:
        print(f"⚠️ Date validation issues: {validation_result}")

    # 4. Check for Issues & Log
    flags = check_for_issues(fields, confidence)
    if flags:
        print(f"⚠️ Flags raised: {flags}")
    
    doc_id = os.path.basename(file_path).split('.')[0] if '.' in os.path.basename(file_path) else "DOC_001"
    
    # Create final JSON structure
    final_output = create_json_output(doc_id, fields, confidence, flags)
    
    # Log it
    log_file = log_extraction(doc_id, fields, confidence, validation_result, flags)
    print(f"📝 Logged to extraction_logs.json")
    
    # 5. Output Result
    print("\n--- Final Output (JSON) ---")
    print(json.dumps(final_output, indent=2))

if __name__ == "__main__":
    main()
