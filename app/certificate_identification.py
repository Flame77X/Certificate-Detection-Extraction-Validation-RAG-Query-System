import re

def is_certificate(file_type, text_content):
    """
    Check if document is a certificate based on file type and keyword usage.
    
    Args:
        file_type (str): The extension or type of the file (e.g., 'pdf', 'png').
        text_content (str): The raw text content extracted from the document.

    Returns:
        bool: True if it is likely a certificate, False otherwise.
    """
    
    # Allows common document and image formats
    valid_types = ['pdf', 'jpg', 'png', 'jpeg', 'tiff', 'bmp', 'txt']
    if file_type.lower().replace('.', '') not in valid_types:
        return False
    
    # Check for certificate keywords
    keywords = [
        'certificate', 
        'issued by', 
        'valid until', 
        'expiry', 
        'issued on', 
        'expires', 
        'certification',
        'certify',
        'awarded to',
        'completion',
        'achievement'
    ]
    
    text_lower = text_content.lower()
    # Count how many unique keywords appear in the text
    found_keywords = sum(1 for kw in keywords if kw in text_lower)
    
    # If at least 2 keywords found, it's likely a certificate
    if found_keywords >= 2:
        return True
        
    # Fallback: Handle text with extra spaces (e.g., "C e r t i f i c a t e")
    # Remove all spaces from text and check against space-less keywords
    text_nospace = text_lower.replace(' ', '')
    keywords_nospace = [k.replace(' ', '') for k in keywords]
    
    found_keywords_nospace = sum(1 for kw in keywords_nospace if kw in text_nospace)
    
    return found_keywords_nospace >= 2
