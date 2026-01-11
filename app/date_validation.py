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
