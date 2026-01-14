# Security Deep Dive: batch_processor.py

**Target File:** `batch_processor.py`
**Review Date:** 2026-01-12
**Severity:** HIGH

---

## 1. Input Validation
### Analysis
- **CSV Input:** The script accepts a CSV file path via `argparse`.
- **File Paths:** It reads file paths from the CSV rows (`row[0]`) and directly passes them to `process_single_file`.
- **Vulnerabilities:**
    - **Path Traversal (Critical):** There is **ZERO validation** on the file paths found in the CSV. A malicious CSV could contain paths like `C:\Windows\System32\drivers\etc\hosts` or `../../.env`. The script checks `os.path.exists()` and then proceeds to read/process it.
    - **CSV Bomb (Medium):** No limit on the number of rows. A 10GB CSV could crash the system (DoS).

### Fix Example
```python
import os

ALLOWED_ROOT = os.path.abspath("./data")

def validate_path(path):
    # Resolve absolute path
    abs_path = os.path.abspath(path)
    # Check if it starts with allowed root
    if not abs_path.startswith(ALLOWED_ROOT):
        print(f"❌ Security Block: {path} is outside data directory.")
        return None
    return abs_path
```

---

## 2. Authentication & Authorization
### Analysis
- **Environment:** Use `load_dotenv()` on line 10.
- **Handling:** It doesn't handle keys itself but imports `extract_with_azure` from `app.field_extraction`.
- **Verdict:** ✅ **Safe**. Credentials are not hardcoded in this file.

---

## 3. Data Exposure
### Analysis
- **Output:** Writes full extraction results to `batch_results.json` (Lines 88-90).
- **Sensitive Data:** This JSON includes PII (Name, Cert Number, Dates).
- **Logging:** Console output prints absolute paths `--- Processing: {file_path} ---`.
- **Vulnerabilities:**
    - **PII Leakage (High):** `batch_results.json` is storing sensitive personally identifiable information in plain text.
    - **Path Disclosure (Low):** Console logs reveal directory structure.

### Fix Example
```python
# Create a sanitized version of results before dumping
sanitized_results = []
for res in results:
    safe_res = res.copy()
    # Mask sensitive fields
    if 'fields' in safe_res:
         safe_res['fields']['certificate_number'] = "REDACTED"
    sanitized_results.append(safe_res)
    
json.dump(sanitized_results, f)
```

---

## 4. Code Injection
### Analysis
- **Parsing:** Uses standard `csv.reader` and `json.dump`.
- **Execution:** No `eval()`, `exec()`, or `subprocess.call` on user input.
- **Verdict:** ✅ **Safe**. Standard libraries prevent typical injection vulnerabilities here.

---

## 5. Dependency Security
### Analysis
- **Imports:** `csv`, `json`, `os`, `argparse`, `datetime`, `dotenv`.
- **Local Imports:** `app.ocr_module`, `app.field_extraction`.
- **Risk:** Relies on `python-dotenv`. If that library handles `.env` insecurely (rare), it could be an issue.
- **Verdict:** ✅ **Safe**, assuming standard pip packages.

---

## Summary of Findings

| Vulnerability | Severity | Line # | Check |
| :--- | :--- | :--- | :--- |
| **Path Traversal** | 🔴 **CRITICAL** | 23, 31, 82 | `row[0]` used directly |
| **PII Logging** | 🟠 **HIGH** | 90 | `json.dump(results)` |
| **Unbounded Loop** | 🟡 **MEDIUM** | 75 | `for row in reader` |

## Final Recommendation
**This file is NOT safe for production use with untrusted CSV inputs.** You MUST implement the Path Validation fix immediately.
