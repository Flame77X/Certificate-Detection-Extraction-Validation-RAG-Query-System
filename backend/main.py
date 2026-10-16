import os
import json
import argparse

# batch_processor loads .env before importing the app modules
from batch_processor import process_single_file
from app.security import BACKEND_DIR

def main():
    parser = argparse.ArgumentParser(description="Certificate Extraction & Validation System (Part A)")
    parser.add_argument("--file", help="Path to the certificate file (must be under backend/data)",
                        default=os.path.join(BACKEND_DIR, "data", "sample_certificate.txt"))
    args = parser.parse_args()

    # Same pipeline as the web API and batch runner (OCR -> identify -> extract -> validate -> status)
    final_output = process_single_file(args.file)
    if not final_output:
        print("❌ No result. See messages above (file missing, outside data/, or not a certificate).")
        return

    print(f"🏢 Issuer Status: {final_output['issuer_validation']['status']}")
    print(f"🏁 Final Certificate Status: {final_output['final_status']}")
    if final_output['confidence_flags']:
        print(f"⚠️ Flags raised: {final_output['confidence_flags']}")
    print("📝 Logged to extraction_logs.json")

    print("\n--- Final Output (JSON) ---")
    print(json.dumps(final_output, indent=2))

if __name__ == "__main__":
    main()
