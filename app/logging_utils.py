import json
from datetime import datetime
import os

LOG_FILE = 'extraction_logs.json'

def log_extraction(doc_id, fields, confidence, date_validation, flags):
    """
    Log extraction results to a JSON line file.
    
    Args:
        doc_id (str): Unique identifier for the document.
        fields (dict): Extracted fields.
        confidence (dict): Confidence scores for fields.
        date_validation (dict): Results of date validation.
        flags (list): List of any warning flags raised.
        
    Returns:
        dict: The log entry that was written.
    """
    
    log_entry = {
        "doc_id": doc_id,
        "timestamp": datetime.now().isoformat(),
        "stage": "extraction_validation",
        "extracted_fields": fields,
        "confidence_scores": confidence,
        "date_validation": date_validation,
        "confidence_flags": flags,
        "needs_manual_review": len(flags) > 0
    }
    
    # Write to log file (append mode)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        print(f"Error writing to log file: {e}")
    
    return log_entry

def check_for_issues(fields, confidence):
    """
    Flag any problems with extraction such as missing fields or low confidence.
    
    Args:
        fields (dict): Extracted fields.
        confidence (dict): Confidence scores.
        
    Returns:
        list: A list of issue flags (strings).
    """
    
    flags = []
    
    # Check for missing fields
    if fields:
        for field, value in fields.items():
            if not value:
                flags.append(f"MISSING_{field.upper()}")
    
    # Check for low confidence (< 0.80)
    if confidence:
        for field, conf in confidence.items():
            if conf < 0.80:
                flags.append(f"LOW_CONFIDENCE_{field.upper()}")
            
    return flags
