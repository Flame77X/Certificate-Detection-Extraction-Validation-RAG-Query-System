# Security Audit Report

**Date:** 2026-01-12
**Project:** Certificate Extraction System
**Auditor:** Antigravity Agent

## Executive Summary
The system is functional and uses basic security practices like `.env` for secrets. However, there are **High** and **Medium** risks related to **Path Traversal**, **Data Leakage (PII)**, and **Denial of Service (DoS)** vectors in the batch processing capability.

---

## 🚨 Critical / High Vulnerabilities

### 1. Path Traversal & Arbitrary File Access (High)
**Location:** `main.py` (line 21), `batch_processor.py` (lines 77, 82), `app/ocr_module.py` (line 8)
**Risk:** Malicious inputs (e.g., `../../windows/system32/secrets.txt`) could allow an attacker to attempt reading sensitive files on the host system if the application runs with elevated privileges or simply verify file existence.
**Fix:** Sanitize file paths to ensure they are within a specific "allowed" data directory.

```python
# Secure Implementation Example
import os

ALLOWED_DIR = os.path.abspath("./data")

def validate_path(user_path):
    abs_path = os.path.abspath(user_path)
    if not abs_path.startswith(ALLOWED_DIR):
        raise VueError("Access denied: File outside data directory")
    return abs_path
```

### 2. Sensitive Data Leakage in Logs (High)
**Location:** `app/logging_utils.py` (line 35) -> `extraction_logs.json`
**Risk:** The system logs *extracted fields* (Name, Certificate Number) in plain text. This is a privacy violation (GDPR/CCPA) if personal certificates are processed. JSON logs are not encrypted.
**Fix:** Redact PII from logs or hash sensitive fields.

```python
# app/logging_utils.py fix
def log_extraction(...):
    # Create a copy and redact
    safe_fields = fields.copy()
    if 'certificate_number' in safe_fields:
        safe_fields['certificate_number'] = '***REDACTED***'
    
    log_entry = { ..., "extracted_fields": safe_fields, ... }
```

---

## ⚠️ Medium Vulnerabilities

### 3. Missing API Timeouts (Medium)
**Location:** `app/field_extraction.py` (line 69)
**Risk:** The `client.chat.completions.create` call has no timeout. If Azure hangs, the application hangs indefinitely, potentially causing a Denial of Service (DoS).
**Fix:** Add a timeout parameter.

```python
response = client.chat.completions.create(
    ...,
    timeout=30.0 # 30 seconds limit
)
```

### 4. Batch Processing DoS (Medium)
**Location:** `batch_processor.py` (line 75)
**Risk:** The script reads *all* lines from the CSV and processes them without limits. A malicious CSV with 1,000,000 lines could exhaust API credits ($$$) and memory.
**Fix:** Implement a batch limit.

```python
MAX_BATCH_SIZE = 50
if len(valid_files) > MAX_BATCH_SIZE:
    raise ValueError(f"Batch size limit exceeded ({MAX_BATCH_SIZE})")
```

### 5. Unpinned Dependencies (Medium)
**Location:** `requirements.txt`
**Risk:** Dependencies (like `pypdf`, `openai`) do not have version numbers. Future updates might introduce breaking changes or security vulnerabilities.
**Fix:** Pin versions.

```text
openai==1.12.0
pypdf==4.0.1
python-dotenv==1.0.1
```

---

## ℹ️ Low Vulnerabilities

### 6. Exception Information Leakage (Low)
**Location:** `app/field_extraction.py` (line 99), `main.py` (line 43)
**Risk:** Printing raw exception strings (`{e}`) can sometimes leak internal paths or API key fragments (rare but possible).
**Fix:** Log generic error messages to user, detailed errors to secure log.

```python
print(f"❌ Error during extraction. See admin logs for details.")
# logging.error(e) # to secure file
```

---

## ✅ Security Scorecard

| Category | Status | Notes |
| :--- | :--- | :--- |
| **API Key Security** | 🟢 Good | Keys managed via `.env` and `.gitignore`. |
| **Input Validation** | 🔴 Fail | No path validation. |
| **Data Privacy** | 🟠 Warning | PII logged in plain text. |
| **Dependency Mgmt** | 🟠 Warning | Unpinned versions. |
| **HTTPS/In-Transit** | 🟢 Good | Azure SDK uses TLS 1.2+. |
