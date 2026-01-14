def assign_certificate_status(extraction_data, validation_results, issuer_validation):
    """
    Assign final certificate status based on all validations
    
    Returns one of:
    - "Verified" (all checks passed)
    - "Expired" (expiry date in past)
    - "Untrusted Issuer" (issuer not in trusted list)
    - "Verification Failed" (validation failed)
    - "Manual Review Required" (low confidence or incomplete data)
    """
    
    # 1. Check Confidence
    confidence_scores = extraction_data.get('confidence', {})
    if not confidence_scores:
        return "Manual Review Required"
    
    # Calculate average confidence
    avg_confidence = sum(confidence_scores.values()) / len(confidence_scores)
    
    if avg_confidence < 0.7:
        return "Manual Review Required"
    
    # 2. Check Issuer
    if not issuer_validation.get('is_trusted', False):
        return "Untrusted Issuer"
    
    # 3. Check Expiry
    if validation_results.get('expiry_status') == 'expired':
        return "Expired"
    
    # 4. Check Critical Fields
    critical_fields = ['issuer', 'issued_date', 'subject']
    fields = extraction_data.get('fields', {})
    missing = [f for f in critical_fields if not fields.get(f)]
    
    if missing:
        return "Manual Review Required"
    
    # 5. Check Date Validation
    if not validation_results.get('issued_date_valid', True):
        return "Verification Failed"
    
    # ✅ All checks passed
    return "Verified"
