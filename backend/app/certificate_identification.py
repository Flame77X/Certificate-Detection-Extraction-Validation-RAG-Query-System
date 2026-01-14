import re

def is_certificate(file_type, text_content):
    """
    Enhanced certificate detection with multiple strategies
    """
    
    # Validate file type
    valid_types = ['pdf', 'jpg', 'png', 'jpeg', 'tiff', 'bmp', 'txt', 'gif']
    if file_type.lower().replace('.', '') not in valid_types:
        return False
    
    text_lower = text_content.lower()
    
    # Strategy 1: Primary certificate keywords
    primary_keywords = [
        'certificate',
        'certification',
        'certify',
        'certified',
        'diploma'
    ]
    
    # Strategy 2: Formal certificate phrases
    formal_phrases = [
        'to whomsoever it may concern',
        'this is to certify that',
        'has completed',
        'is hereby awarded',
        'this is to confirm',
        'completion certificate',
        'achievement certificate',
        'certificate of',
        'award',
        'completion of',
    ]
    
    # Strategy 3: Dates (certificates often have issue/expiry dates)
    # Added short months (jan, feb, etc.)
    date_pattern = r'\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec'
    date_found = len(re.findall(date_pattern, text_lower)) >= 2
    
    # Strategy 4: Certificate fields
    field_keywords = [
        'issued',
        'issue date',
        'expiry',
        'expires',
        'expiration',
        'valid until',
        'issuer',
        'issued by',
        'issued on',
        'date',
        'signature',
        'authorized',
        'validation number',
        'validate at'
    ]
    
    # Count matches
    primary_count = sum(1 for kw in primary_keywords if kw in text_lower)
    formal_count = sum(1 for phrase in formal_phrases if phrase in text_lower)
    field_count = sum(1 for kw in field_keywords if kw in text_lower)
    
    # Decision logic (improved):
    # Option A: Has primary keyword + formal phrase = CERTIFICATE
    if primary_count >= 1 and formal_count >= 1:
        return True
    
    # Option B: Has multiple formal phrases = CERTIFICATE
    if formal_count >= 2:
        return True
    
    # Option C: Has dates + multiple field keywords = CERTIFICATE
    if date_found and field_count >= 3:
        return True
    
    # Option D: Has primary keyword + dates = CERTIFICATE
    if primary_count >= 1 and date_found:
        return True
    
    # Option E: Multiple field keywords (3+) = CERTIFICATE
    if field_count >= 3:
        return True
    
    # Otherwise: Not a certificate
    return False
