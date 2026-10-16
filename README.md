# 📚 Certificate Intelligence & Verification System (CIVS)

[![Production Ready](https://img.shields.io/badge/Status-Production--Ready-brightgreen.svg)](https://github.com/Flame77X/Certificate-Detection-Extraction-Validation-RAG-Query-System)
[![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![AI Powered](https://img.shields.io/badge/AI-Azure--OpenAI-orange.svg)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)

A production-grade, end-to-end system for **AI-powered certificate detection, field extraction, validation, and RAG-based querying**. This system transforms unstructured certificate documents (PDFs, Images) into structured, verifiable intelligence.

---

## 📖 Table of Contents
1. [🌟 Key Features](#-key-features)
2. [🏗️ System Architecture](#️-system-architecture)
3. [🚀 Quick Start (5 Minutes)](#-quick-start-5-minutes)
4. [🛠️ Installation & Setup](#️-installation--setup)
5. [💻 Usage Guide](#-usage-guide)
    - [Option A: Web API (Flask)](#option-a-web-api-flask)
    - [Option B: Single File (CLI)](#option-b-single-file-cli)
    - [Option C: Batch Processing](#option-c-batch-processing)
6. [🧠 RAG Query System](#-rag-query-system)
7. [🛡️ Security & Compliance](#️-security--compliance)
8. [⚙️ Configuration](#️-configuration)
9. [❓ FAQ & Troubleshooting](#-faq--troubleshooting)

---

## 🌟 Key Features

- **✅ Smart Identification**: Automatically detects if a document is a certificate using multi-layered keyword and context analysis.
- **🧠 5-Field Intelligent Extraction**: Uses Azure OpenAI (GPT-4 class, JSON mode) with a self-consistency engine (3 parallel runs, majority vote; confidence = share of runs that agree) to extract:
  - `issuer`, `certificate_number`, `issued_date`, `expiry_date`, `subject`
- **🛡️ Multi-Level Validation**:
  - **Date Logic**: Ensures `issued_date` < `expiry_date` and validates formats.
  - **Issuer Verification**: Cross-references against a `trusted_issuers.json` whitelist (case/punctuation/legal-suffix normalised, strict fuzzy match for OCR typos).
- **📄 OCR**: Text PDFs via `pypdf`; images (JPG/PNG) and scanned PDFs (embedded page images) via the Azure OpenAI vision model.
- **📚 RAG (Retrieval-Augmented Generation)**: Store extracted certificates in a ChromaDB vector database and query them using natural language. Answers cite certificate IDs and return the retrieved sources.
- **📊 Production Ready**: Comprehensive logging (JSONL), security protections (PII redaction, Path traversal), and batch processing capabilities.

---

## 🏗️ System Architecture

```mermaid
graph TD
    A[Certificate File] --> B{OCR Module}
    B -->|Text PDF| C[pypdf]
    B -->|Image/Scanned| D[GPT-4 Vision OCR]
    C --> E[Document Content]
    D --> E
    E --> F{Identification}
    F -->|Not a Cert| G[Reject]
    F -->|Is a Cert| H[Field Extraction]
    H -->|Azure OpenAI| I[Consensus Engine]
    I --> J[Validation Module]
    J -->|Dates/Issuers| K[Status Assignment]
    K --> L[Logs & Result]
    L --> M[(ChromaDB)]
    M --> N[RAG Query System]
    N --> O[Natural Language Answer]
```

---

## 🚀 Quick Start (5 Minutes)

### 1. Install Dependencies
```powershell
pip install -r backend/requirements.txt
```

### 2. Set Up Environment
Copy `.env.example` to `.env` and fill in your Azure keys:
```powershell
cp .env.example .env
```

### 3. Run the Web Interface
```powershell
python backend/app.py
```
Visit `http://localhost:5000` to upload and verify certificates!

---

## 🛠️ Installation & Setup

### Prerequisites
- **Python 3.9+**
- **Azure OpenAI** resource with a vision-capable chat deployment (extraction, OCR, RAG answers) and an embedding deployment (RAG search)

### Detailed Steps
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Flame77X/Certificate-Detection-Extraction-Validation-RAG-Query-System.git
   cd Certificate-Detection-Extraction-Validation-RAG-Query-System
   ```
2. **Environment Configuration**:
   Edit your `.env` file:
   ```env
   AZURE_OPENAI_API_KEY=your_key
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT=gpt-4o
   AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-small
   ```
   See `.env.example` for optional settings. Without a key, extraction returns nothing; set `USE_MOCK_LLM=1` for an offline demo with fixed mock data.
3. **Storage**: `backend/data/uploads` and the ChromaDB store are created automatically. All processed files must live under `backend/data/`.

---

## � Usage Guide

### Option A: Web API (Flask)
The primary interface for integration. Starting the server is simple:
```bash
python backend/app.py
```
- **Endpoint**: `POST /upload`
- **Payload**: `multipart/form-data` with key `file`.
- **Response**: Full JSON with fields, confidence, and validation status.
- **Endpoint**: `POST /query` with JSON `{"question": "..."}` returns `{"answer": "...", "sources": [{"doc_id", "issuer", "status", "distance"}]}`.

### Option B: Single File (CLI)
Perfect for testing individual files:
```bash
python backend/main.py --file backend/data/sample_certificate.txt
```
The file must be inside `backend/data/` (path sandbox).

### Option C: Batch Processing
Process hundreds of certificates from a CSV list:
```bash
python backend/batch_processor.py --csv backend/data/batch_test.csv
```
One file path per CSV row (relative paths resolve against `backend/`, max 50 rows). Results are saved to `backend/batch_results.json` with PII redacted.

### Running Tests
```bash
cd backend
python -m unittest discover -s tests -p "test_*.py"
```
Tests mock Azure OpenAI; no keys or network needed.

---

## 🧠 RAG Query System

The system includes a built-in "Memory" using **ChromaDB**. Once a certificate is processed, its metadata and searchable text are ingested into a vector database.

**What you can ask:**
- *"Who issued the AWS Solution Architect certificate?"*
- *"When does the ISO certificate expire?"*
- *"Are there any certificates from Global Tech Institute?"*

**Implementation:**
- **Vector DB**: ChromaDB (Persistent)
- **Embeddings**: Azure OpenAI deployment from `AZURE_EMBEDDING_DEPLOYMENT`. Certificates are not indexed when embeddings are unavailable.
- **Query Engine**: GPT-4 (for answering based on retrieved context)

---

## 🛡️ Security & Compliance

Developed with enterprise security in mind:
- **🔒 Path Traversal Protection**: Upload names pass through `secure_filename`; every processed file must resolve inside `backend/data/`.
- **🕵️ PII Redaction**: Certificate numbers, subjects and ID-like fields are masked in logs and batch output.
- **📄 Format Lockdown**: Uploads accept `pdf`, `png`, `jpg`, `jpeg`, `txt` only, max 10 MB.
- **🧱 Prompt-Injection Guarding**: Certificate text and retrieved records are passed to the model as data with instructions to ignore embedded commands; UI escapes all model output.
- **🔑 Secret Management**: API keys are never logged; timeouts prevent resource exhaustion.

---

## ⚙️ Configuration

### Trusted Issuers
Edit `backend/trusted_issuers.json` to manage your whitelist:
```json
{
  "trusted_issuers": [
    "AWS Training",
    "ISO Authority",
    "Microsoft Training"
  ]
}
```

### Limits
`MAX_FILE_SIZE_MB = 10` and `MAX_BATCH_SIZE = 50` in `backend/app/security.py`.

---

## ❓ FAQ & Troubleshooting

**Q: Why is my document classified as "NOT a certificate"?**
**A**: Ensure your document contains keywords like "Certify", "Diploma", or "Awarded". You can adjust these in `backend/app/certificate_identification.py`.

**Q: Extraction confidence is low.**
**A**: Confidence is the share of the 3 extraction runs that agree. Low values mean the model gave different answers, usually because of a poor scan or ambiguous text. Check the OCR text and image quality.

**Q: RAG System is "offline".**
**A**: Check your `.env` for `AZURE_EMBEDDING_DEPLOYMENT` and ensure the embeddings model is correctly deployed in your Azure portal.

---

## � Project Structure

```text
├── backend/
│   ├── app.py                # Flask API & Frontend Host
│   ├── main.py               # CLI Entry Point
│   ├── batch_processor.py    # Batch Handling Logic
│   ├── app/                  # Core Logic Modules
│   │   ├── ocr_module.py     # Text & Graphics OCR
│   │   ├── field_extraction.py # AI Extraction Engine
│   │   ├── rag_pipeline.py   # Vector Search & QA
│   │   └── ...               # Security, Validation, Logging
│   └── data/                 # Local Storage (Logs, Uploads, Vector DB)
├── frontend/
│   ├── templates/            # index.html
│   └── static/               # CSS and Assets
└── requirements.txt          # System Dependencies
```

---

*Built with ❤️ for secure, intelligent certificate management.*
