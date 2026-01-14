import csv
import json
import os
import argparse
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import existing modules
# Import existing modules
from app.ocr_module import extract_text_from_file
from app.certificate_identification import is_certificate
from app.field_extraction import extract_with_azure, extract_fields, create_json_output
from app.date_validation import validate_dates, validate_issuer
from app.logging_utils import log_extraction, check_for_issues
from app.security import validate_secure_path, MAX_BATCH_SIZE, redact_pii
from app.status_assignment import assign_certificate_status
from app.external_verification import verify_external_issuer

def process_single_file(file_path):
    """Run the entire extraction pipeline on a single file"""
    print(f"--- Processing: {file_path} ---")
    
    # Security: Path validation handled inside extract_text_from_file -> validate_secure_path
    pass 
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None

    # 1. Identification
    file_ext = file_path.split('.')[-1].lower()
    
    # Use centralized extraction module
    # Note: validate_secure_path is called inside here now
    try:
        text_content, used_ocr = extract_text_from_file(file_path)
    except Exception as e:
        print(f"⛔ Security/Error: {e}")
        return None

    if not text_content:
        print("⚠️  No text could be extracted.")

    # Check identification
    is_valid = is_certificate(file_ext, text_content)
    if not is_valid:
        print("❌ Document is NOT classified as a certificate.")
        return None

    print("✅ Identified as certificate.")

    # 2. Extraction
    print("⏳ Extracting fields...")
    extractor_output = extract_with_azure(text_content)
    fields, confidence = extract_fields(extractor_output)

    # 3. Validation
    val_result = validate_dates(fields.get('issued_date'), fields.get('expiry_date'))
    
    # New: Issuer Validation
    issuer_validation = validate_issuer(fields.get('issuer'))
    
    # 4. JSON & Logging
    flags = check_for_issues(fields, confidence)
    doc_id = os.path.basename(file_path).split('.')[0]
    
    # Extract voting debug info if present (Available for debug if needed, but not logged)
    voting_details = extractor_output.get('_voting_debug', {})
    
    # output = create_json_output(doc_id, fields, confidence, flags) # Old call
    # We need to log it. Let's pass it to log_extraction
    log_extraction(doc_id, fields, confidence, val_result, flags)
    
    output = create_json_output(doc_id, fields, confidence, flags)
    
    # New: Final Status
    final_status = assign_certificate_status(output, val_result, issuer_validation)
    
    # --- TASK 7 IMPLEMENTATION: External Verification ---
    # If standard validation says "Untrusted Issuer", we try External API
    external_verification = None
    
    if final_status == "Untrusted Issuer" or issuer_validation['status'] == 'Untrusted Issuer':
        print("🔍 Internal validation failed. Attempting Task 7: External Verification...")
        external_stats = verify_external_issuer(fields.get('issuer'), fields)
        
        # Override final status if external check returned a decisive status
        if "Verified" in external_stats['status']:
            final_status = "Verified"
            issuer_validation['status'] = "Verified via External API"
        elif "Manual" in external_stats['status']:
            final_status = "Manual Review Required"
            
        external_verification = external_stats

    output['validation'] = val_result
    output['issuer_validation'] = issuer_validation
    output['external_verification'] = external_verification
    output['final_status'] = final_status
    # output['voting_analysis'] = voting_details 
    
    return output

def process_batch(csv_file):
    """Read a CSV and process all files listed"""
    results = []
    
    # Security: Validate CSV path
    try:
        csv_file = validate_secure_path(csv_file)
    except Exception as e:
        print(f"⛔ Security Error: {e}")
        return

    print(f"🚀 Starting Batch Processing from: {csv_file}")
    
    valid_files = []
    with open(csv_file, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                valid_files.append(row[0])
                
    # Security: DoS Protection
    if len(valid_files) > MAX_BATCH_SIZE:
         print(f"⛔ Batch too large! Limit is {MAX_BATCH_SIZE}. Found: {len(valid_files)}")
         return

    print(f"Found {len(valid_files)} files to process.\n")

    for file_path in valid_files:
        # Security: Allow relative paths in CSV to be resolved against data dir if needed
        # But our simple validator expects absolute or correct relative paths.
        # Let's rely on process_single_file calling extract_text_from_file which validates it.
        result = process_single_file(file_path.strip())
        if result:
            results.append(result)
        print("-" * 30)

    # Save Batch Results
    output_file = 'batch_results.json'
    
    # Security: Redact PII in Batch Output
    safe_results = []
    for res in results:
        res_copy = res.copy()
        if 'fields' in res_copy:
            res_copy['fields'] = redact_pii(res_copy['fields'])
        safe_results.append(res_copy)
        
    with open(output_file, 'w') as f:
        json.dump(safe_results, f, indent=2)

    print(f"\n✅ Batch Processing Complete.")
    print(f"📄 Results saved to: {output_file} (PII Redacted)")
    print(f"📊 Processed {len(results)}/{len(valid_files)} certificates successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Batch process certificates from CSV')
    parser.add_argument('--csv', default='data/batch_test.csv', help='Path to CSV file containing file paths')
    args = parser.parse_args()
    
    process_batch(args.csv)
