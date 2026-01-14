# Secure File Handling Guide

**Review Target:** `app/ocr_module.py` & `batch_processor.py`
**Date:** 2026-01-12

---

## 1. 📂 Input Validation & Path Traversal

### The Risk
Currently, your code accepts **any** file path provided by the user.
*   Attack: `python main.py --file ../../../etc/passwd`
*   Attack: Batch CSV containing `C:\Windows\System32\config\SAM`

### Security Checklist
- [x] **Fail**: Do paths stay within a permitted directory?
- [x] **Fail**: Is the filename sanitized (no null bytes, no `../`)?
- [x] **Fail**: Do you check for "Magic Numbers" (real file type) vs User extensions?

### ✅ Secure Implementation Example
Create a strict validator in `app/ocr_module.py` or a utility file.

```python
import os

REQUIRED_DATA_DIR = os.path.abspath("data")

def validate_secure_path(user_path):
    # 1. Resolve to absolute path
    safe_path = os.path.abspath(user_path)
    
    # 2. Check traversal (Must be inside data/)
    if not os.path.commonpath([safe_path, REQUIRED_DATA_DIR]) == REQUIRED_DATA_DIR:
        raise PermissionError(f"Security Alert: Attempted header path traversal to {user_path}")
        
    # 3. Check existence
    if not os.path.exists(safe_path):
        raise FileNotFoundError(f"File not found: {user_path}")
        
    return safe_path
```

---

## 2. 💣 PDF Processing & Denial of Service (DoS)

### The Risk
*   **PDF Bombs**: A small 10KB PDF can expand to 10GB in memory, crashing your server.
*   **Infinite Loops**: Malformed PDFs can cause parsers (`pypdf`) to hang.
*   **Memory Exhaustion**: Reading a 5GB `.txt` file with `f.read()` (Line 23 of `ocr_module.py`) creates a 5GB string in RAM.

### Security Checklist
- [x] **Fail**: Is there a file size limit (e.g., 10MB)?
- [x] **Fail**: Do you read text files in chunks?
- [x] **Pass**: `pypdf` is generally safe against code execution (unlike `pickle`), but vulnerable to parser bugs.

### ✅ Secure Implementation Example

**Size Limit Check:**
```python
MAX_FILE_SIZE_MB = 10

def check_file_size(file_path):
    size_bytes = os.path.getsize(file_path)
    if size_bytes > (MAX_FILE_SIZE_MB * 1024 * 1024):
        raise ValueError(f"File too large. Limit is {MAX_FILE_SIZE_MB}MB")
```

**Safe Text Reading (Chunking):**
```python
# Instead of f.read()
with open(file_path, 'r', encoding='utf-8') as f:
    # Read first 1MB only
    text_content = f.read(1_000_000) 
```

---

## 3. 🔎 File Type Validation (Magic Numbers)

### The Risk
Use relies on `.split('.')[-1]`. I can rename `virus.exe` to `virus.txt` and your system will try to read it. While reading an EXE as text usually just fails, it's bad practice.

### ✅ Secure Implementation Example
Use `python-magic` or check headers manually.

```python
def is_safe_pdf(file_path):
    with open(file_path, 'rb') as f:
        header = f.read(4)
        # PDF Magic Number is %PDF
        if header != b'%PDF':
            raise ValueError("Invalid file. Header does not match PDF signature.")
```

---

## 4. 🗄️ Output Files & Permissions

### The Risk
*   **World Readable**: Default permissions on Linux/Unix might be `644` (readable by everyone).
*   **Overwrite**: `batch_processor.py` blindly overwrites `batch_results.json`. If multiple users run batches, they destroy each other's work or experience race conditions.

### ✅ Secure Implementation Example
*   Use unique filenames (UUIDs or Timestamps).
*   Set explicit permissions if running on a shared server.

---

## Summary of Immediate Fixes

1.  **Enforce `data/` directory**: Stop users from reading system files.
2.  **Add Size Limit**: Reject files > 10MB.
3.  **Read Limit**: Stop reading text files after 50 Pages / 100KB to prevent memory crashes.

**Would you like me to update `app/ocr_module.py` to include these Path and Size safety checks?**
