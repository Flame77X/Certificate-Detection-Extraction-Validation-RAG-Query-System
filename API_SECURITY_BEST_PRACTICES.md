# Azure OpenAI API Security: Best Practices & Review

**Review Target:** `app/field_extraction.py`
**Date:** 2026-01-12

---

## 1. 🔑 Credential Management

### Best Practice
*   **NEVER** hardcode keys in Python files.
*   Use Environment Variables loaded from a `.env` file that is **excluded** from Git (`.gitignore`).
*   **Do not** provide "default" keys in your code, even if they look like placeholders.

### Audit of your code (`app/field_extraction.py`)
*   ✅ **GOOD**: You are using `os.getenv("AZURE_OPENAI_API_KEY")`.
*   ✅ **GOOD**: You verify the key exists before calling the API.
*   ✅ **GOOD**: `.env` is listed in your `.gitignore`.
*   ⚠️ **WARNING**: Lines 9-10 have defaults (`gpt-4`, `2024-02-15-preview`). While not secrets, hardcoding configuration makes rotation harder. Move these to `.env` too.

### Secure Implementation
```python
# Load exclusively from environment
api_key = os.getenv("AZURE_OPENAI_API_KEY")
if not api_key:
    raise ValueError("Missing AZURE_OPENAI_API_KEY in environment variables")
```

---

## 2. 🛡️ API Call Security

### Best Practice
*   **HTTPS**: Always use HTTPS (Port 443). The `openai` Python library does this automatically.
*   **Certificate Validation**: Never disable verify_ssl (default is True).
*   **Endpoints**: Store the full endpoint URL in `.env`.

### Audit of your code
*   ✅ **GOOD**: You are using the official `AzureOpenAI` client which enforces HTTPS and SSL validation by default.
*   ✅ **GOOD**: Endpoint is loaded from env `AZURE_OPENAI_ENDPOINT`.

---

## 3. 🚨 Error Handling & Reliability

### Best Practice
*   **Timeouts**: APIs can hang. Always set a timeout (e.g., 30s) to prevent DoS.
*   **Clean Logs**: Catch 401 (Auth) vs 429 (Rate Limit) errors specifically.
*   **No Leakage**: Never print the full `exception` object to end-users (it might contain the key or URL params).

### Audit of your code
*   🔴 **CRITICAL**: **No timeout specified**. If Azure hangs, your script hangs forever.
*   ⚠️ **WARNING**: `print(f"❌ Azure OpenAI Error: {e}")` (Line 99). This is locally okay for debugging but risky in production logs.

### Secure Implementation
```python
try:
    response = client.chat.completions.create(
        model=deployment,
        messages=...,
        timeout=20.0  # <--- FIX: Add Timeout
    )
except openai.AuthenticationError:
    log_secure("Auth failed. Check API Keys.") # Don't log the key!
except openai.RateLimitError:
    log_secure("Rate limit exceeded. Retrying...")
except Exception as e:
    log_secure("An unexpected API error occurred") # Generic message
```

---

## 4. 🔒 Data Privacy in Transit

### Best Practice
*   **Encryption**: Azure OpenAI uses TLS 1.2+ for transit (Automatic).
*   **Logging**: **NEVER** log the full JSON response if it contains PII (Personally Identifiable Information).
*   **Retention**: Zero Data Retention (ZDR) policy is available for Enterprise Azure customers. Check your specific Azure subscription policies.

### Audit of your code
*   ⚠️ **RISK**: The script sends the *entire* document text to the cloud. This is necessary for functionality, but ensure you trust the Azure endpoint (it must be your private instance, not a public proxy).

---

## 5. 🔄 Key Rotation Strategy

### Best Practice
*   **Rotation Schedule**: Rotate keys every 90 days.
*   **Process**:
    1.  Generate **Key 2** in Azure Portal.
    2.  Update `.env` on your server with Key 2.
    3.  Restart Application.
    4.  Verify functionality.
    5.  Revoke/Regenerate **Key 1** in Azure.
*   **Dev/Prod**: Use separate Azure resources for Development and Production. Never share keys.

---

## Summary of Fixes for You

1.  **Add Timeout**: Update `field_extraction.py` line 69 to include `timeout=30`.
2.  **Sanitize Exceptions**: Change line 99 to log a generic error instead of the raw exception object.
3.  **Rotate Keys**: Go to Azure Portal -> Your OpenAI Resource -> Keys & Endpoint -> Regenerate Key 1. Update your `.env`.
