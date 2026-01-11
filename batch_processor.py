import csv
import json
import os
import argparse
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import existing modules
from app.ocr_module import extract_text_from_file
from app.certificate_identification import is_certificate
from app.field_extraction import extract_with_azure, extract_fields, create_json_output
from app.date_validation import validate_dates
from app.logging_utils import log_extraction, check_for_issues

def process_single_file(file_path):
    """Run the entire extraction pipeline on a single file"""
    print(f"--- Processing: {file_path} ---")
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None

    # 1. Identification
    file_ext = file_path.split('.')[-1].lower()
    
    # Use centralized extraction module
    text_content, used_ocr = extract_text_from_file(file_path)
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
    
    # 4. JSON & Logging
    flags = check_for_issues(fields, confidence)
    doc_id = os.path.basename(file_path).split('.')[0]
    
    output = create_json_output(doc_id, fields, confidence, flags)
    
    # Add validation info to output for batch summary
    output['validation'] = val_result
    
    return output

def process_batch(csv_file):
    """Read a CSV and process all files listed"""
    results = []
    
    if not os.path.exists(csv_file):
        print(f"Error: CSV file '{csv_file}' not found.")
        return

    print(f"🚀 Starting Batch Processing from: {csv_file}")
    
    valid_files = []
    with open(csv_file, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                valid_files.append(row[0])

    print(f"Found {len(valid_files)} files to process.\n")

    for file_path in valid_files:
        result = process_single_file(file_path.strip())
        if result:
            results.append(result)
        print("-" * 30)

    # Save Batch Results
    output_file = 'batch_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Batch Processing Complete.")
    print(f"📄 Results saved to: {output_file}")
    print(f"📊 Processed {len(results)}/{len(valid_files)} certificates successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Batch process certificates from CSV')
    parser.add_argument('--csv', default='data/batch_test.csv', help='Path to CSV file containing file paths')
    args = parser.parse_args()
    
    process_batch(args.csv)
