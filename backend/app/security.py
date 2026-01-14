import os
import re

# Security Constants
MAX_FILE_SIZE_MB = 10
MAX_BATCH_SIZE = 50
ALLOWED_DATA_DIR = os.path.abspath('data')

def validate_secure_path(file_path):
    """
    Ensure file path is within the allowed data directory and exists.
    Prevents Path Traversal attacks (e.g. ../../etc/passwd).
    """
    # 1. Resolve absolute path
    abs_path = os.path.abspath(file_path)
    
    # 2. Check traversal (Must be inside data/)
    # commonpath ensures it's a subpath of ALLOWED_DATA_DIR
    try:
        if os.path.commonpath([abs_path, ALLOWED_DATA_DIR]) != ALLOWED_DATA_DIR:
            raise PermissionError(f"Security Alert: Attempted path traversal to {file_path}")
    except ValueError:
        # Happens on Windows if drives are different (e.g. C: vs D:)
        raise PermissionError(f"Security Alert: Path {file_path} is on a different drive or invalid")

    # 3. Check existence
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    return abs_path

def check_file_size(file_path):
    """
    Ensure file is not too large (DoS prevention).
    """
    size_bytes = os.path.getsize(file_path)
    if size_bytes > (MAX_FILE_SIZE_MB * 1024 * 1024):
        raise ValueError(f"File too large. Limit is {MAX_FILE_SIZE_MB}MB")

def redact_pii(data_dict):
    """
    Redact sensitive fields from a dictionary (e.g. for logging).
    """
    if not data_dict:
        return {}
        
    safe_copy = data_dict.copy()
    
    # Fields to mask
    sensitive_fields = ['certificate_number', 'subject', 'name', 'recipient']
    
    for key in safe_copy:
        if key.lower() in sensitive_fields or 'id' in key.lower():
            if safe_copy[key]:
                # Keep first 2 chars, mask rest
                val = str(safe_copy[key])
                if len(val) > 2:
                    safe_copy[key] = val[:2] + "***REDACTED***"
                else:
                    safe_copy[key] = "***REDACTED***"
                    
    return safe_copy
