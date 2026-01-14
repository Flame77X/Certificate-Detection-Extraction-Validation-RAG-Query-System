# Dependency Security Analysis

**Date:** 2026-01-12
**Target:** Project Dependencies (`requirements.txt`)

---

## 1. 🔍 Vulnerability Assessment

| Library | Risk Level | Known Issues / Notes |
| :--- | :--- | :--- |
| **`openai`** | 🟢 Low | Standard API client. Ensure you use >1.0.0 to avoid legacy issues. |
| **`python-dotenv`** | 🟢 Low | Simple file reader. Very low attack surface. |
| **`pypdf`** | 🟡 Medium | File parser. Historically prone to "Infinite Loop" DoS with malformed PDFs. **Must be pinned.** |
| **`requests`** | 🟢 Low | The standard for HTTP. Mature and heavily audited. |
| **`chromadb`** | 🟠 High | **Supply Chain Risk**. It pulls in a massive tree (`numpy`, `fastapi`, `uvicorn`). Hard to audit fully. |
| **`sentence-transformers`** | 🟠 High | **Heavy dependency**. Pulls in `torch` (PyTorch) which is huge (700MB+) and historically has had malicious typosquatting variants. |

### ⚠️ Critical Note on RAG Libraries
Using `chromadb` and `sentence-transformers` increases your "Attack Surface" by ~500%.
*   They import complex binary libraries (`numpy`, `torch`).
*   **Vulnerability:** A vulnerability in *any* of their sub-dependencies (e.g., `pillow` used by torch) affects you.

---

## 2. 📌 Version Pinning Strategy

### The Problem
Using `openai>=1.3.0` allows pip to install `1.99.9` tomorrow.
*   **Risk:** Version `1.99.9` could be a malicious takeover or introduce breaking bugs.
*   **Risk:** "It works on my machine" but fails in production because of different versions.

### The Fix: Pin Exact Versions
You must lock your dependencies to specific versions that you have tested.

**Recommended `requirements.txt`:**
```text
openai==1.12.0
python-dotenv==1.0.1
pypdf==4.0.1
requests==2.31.0
chromadb==0.4.22
sentence-transformers==2.3.1
```

---

## 3. ⛓️ Supply Chain Security

### How to Verify Authenticity?
1.  **Use Hash Checking**: Ensure the downloaded file matches the official developer's signature.
2.  **Trusted Sources**: Only install from PyPI (default). Be careful with `--extra-index-url` (often used for PyTorch), as it can lead to "Dependency Confusion" attacks.

**Secure Implementation:**
Generate a `requirements.lock` with hashes using `pip-tools`.

```bash
# Install pip-tools
pip install pip-tools

# Generate secure lock file
pip-compile --generate-hashes requirements.txt
```

---

## 4. 📜 License Compliance

| Library | License | Compatible? |
| :--- | :--- | :--- |
| `openai` | MIT | ✅ Yes |
| `python-dotenv` | BSD-3 | ✅ Yes |
| `pypdf` | BSD-3 | ✅ Yes |
| `requests` | Apache 2.0 | ✅ Yes |
| `chromadb` | Apache 2.0 | ✅ Yes |
| `sentence-transformers` | Apache 2.0 | ✅ Yes |

**Verdict:** All are Permissive (Business Safe). No GPL/Viral licenses found.

---

## 5. ✅ Dependency Security Checklist

1.  [ ] **Pin Versions**: Change `>=` to `==` in `requirements.txt`.
2.  [ ] **Audit Now**: Run `pip-audit` to check for current CVEs.
    ```bash
    pip install pip-audit
    pip-audit -r requirements.txt
    ```
3.  **Audit RAG Stack**: Since you use `sentence-transformers`, verify `torch` isn't downloading from strange mirrors.
4.  **Automate**: Add a GitHub Action to run `pip-audit` on every Pull Request.

---

## Recommended Action
I recommend creating a secured `requirements.txt` immediately with pinned versions to prevent "Dependency Drift".
