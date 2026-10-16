import json
import os
import re
from datetime import datetime
from difflib import SequenceMatcher

def validate_dates(issued_date_str, expiry_date_str):
    """
    Validate certificate dates.
    
    Args:
        issued_date_str (str): Issued date in YYYY-MM-DD format.
        expiry_date_str (str): Expiry date in YYYY-MM-DD format.
        
    Returns:
        dict: Validation results including validity status and consistency.
    """
    
    today = datetime.now().date()
    
    # Parse dates
    try:
        # Handle cases where input might be None or empty
        if not issued_date_str or not expiry_date_str:
             return {
                "issued_date_valid": False,
                "expiry_status": "invalid_format",
                "dates_consistent": False,
                "error": "Missing date values"
            }

        issued_date = datetime.strptime(issued_date_str, '%Y-%m-%d').date()
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
    except ValueError:
        return {
            "issued_date_valid": False,
            "expiry_status": "invalid_format",
            "dates_consistent": False,
            "error": "Could not parse dates. Expected YYYY-MM-DD"
        }
    
    # Check issued date (should not be in future)
    issued_valid = issued_date <= today
    
    # Check expiry date
    if expiry_date < today:
        expiry_status = "expired"
    else:
        expiry_status = "valid"
    
    # Check consistency (Issued should be before Expiry)
    dates_consistent = issued_date <= expiry_date
    
    return {
        "issued_date_valid": issued_valid,
        "expiry_status": expiry_status,
        "dates_consistent": dates_consistent
    }

# Legal-form suffixes that don't change issuer identity ("Acme Pvt Ltd" == "Acme")
_ISSUER_SUFFIXES = {'pvt', 'private', 'ltd', 'limited', 'inc', 'llc', 'corp', 'corporation', 'co', 'plc', 'gmbh'}
# Strict threshold: only absorbs OCR/LLM noise ("Microsft Training"), not different organisations
ISSUER_FUZZY_THRESHOLD = 0.92

def normalize_issuer(name):
    """Casefold, strip punctuation and legal-form suffixes for issuer comparison."""
    words = re.sub(r'[^\w\s]', ' ', str(name or '')).casefold().split()
    while words and words[-1] in _ISSUER_SUFFIXES:
        words.pop()
    return ' '.join(words)

def match_trusted_issuer(issuer_name, trusted_issuers):
    """Return (matched_trusted_name, score) or (None, best_score)."""
    target = normalize_issuer(issuer_name)
    if not target:
        return None, 0.0
    best_name, best_score = None, 0.0
    for trusted in trusted_issuers:
        score = SequenceMatcher(None, target, normalize_issuer(trusted)).ratio()
        if score > best_score:
            best_name, best_score = trusted, score
    if best_score >= ISSUER_FUZZY_THRESHOLD:
        return best_name, round(best_score, 3)
    return None, round(best_score, 3)

def validate_issuer(issuer_name):
    """Validate issuer against trusted issuer list (normalised + strict fuzzy match)"""
    try:
        # Load trusted list from backend root
        filepath = os.path.join(os.path.dirname(__file__), '..', 'trusted_issuers.json')
        with open(filepath, 'r') as f:
            trusted_list = json.load(f)

        matched, score = match_trusted_issuer(issuer_name, trusted_list['trusted_issuers'])
        is_trusted = matched is not None

        return {
            'issuer': issuer_name,
            'is_trusted': is_trusted,
            'matched_issuer': matched,
            'match_score': score,
            'status': 'Valid Issuer' if is_trusted else 'Untrusted Issuer'
        }
    except Exception as e:
        return {
            'issuer': issuer_name,
            'is_trusted': False,
            'status': f'Unable to validate: {str(e)}'
        }
