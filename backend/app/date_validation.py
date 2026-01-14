from datetime import datetime

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
def validate_issuer(issuer_name):
    """Validate issuer against trusted issuer list"""
    import json
    import os
    
    try:
        # Load trusted list from project root
        filepath = os.path.join(os.path.dirname(__file__), '..', 'trusted_issuers.json')
        with open(filepath, 'r') as f:
            trusted_list = json.load(f)
        
        # Check matching
        if not issuer_name:
            is_trusted = False
        else:
            is_trusted = issuer_name in trusted_list['trusted_issuers']
        
        return {
            'issuer': issuer_name,
            'is_trusted': is_trusted,
            'status': 'Valid Issuer' if is_trusted else 'Untrusted Issuer'
        }
    except Exception as e:
        return {
            'issuer': issuer_name,
            'is_trusted': False,
            'status': f'Unable to validate: {str(e)}'
        }
