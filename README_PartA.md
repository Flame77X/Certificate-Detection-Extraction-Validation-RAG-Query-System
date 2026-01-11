# Part A: Certificate Extraction & Date Validation

## Overview
This module detects certificates, extracts key fields using **Azure OpenAI (GPT-4)**, and validates the extracted dates. It is designed to be robust, supporting digital text extraction and providing structured JSON output for downstream systems.

**New in Phase 2:**
- **Batch Processing**: Process multiple certificates at once via CSV.
- **OCR Support**: Centralized extraction architecture ready for Azure Document Intelligence.

## 📂 Project Structure

| Path | Purpose |
| :--- | :--- |
| **`app/`** | Core logic modules. |
| **`data/`** | Sample certificates and batch test data. |
| **`tests/`** | Unit tests. |
| **`main.py`** | **Single File Mode**. Process one certificate. |
| **`batch_processor.py`** | **Batch Mode**. Process hundreds of files from CSV. |
| **`.env`** | **Config**. Stores your Azure Keys. |
| **`requirements.txt`** | Project dependencies. |

## System Architecture

```
Input File (PDF/TXT)
    ↓
Certificate Identification ← Checks keywords & file type
    ↓
OCR Module (Text Extraction)
    ├── Strategy 1: PyPDF (Digital Text)
    └── Strategy 2: Azure OCR Fallback (Scanned Images)
    ↓
Field Extraction ← Azure OpenAI (GPT-4)
    ↓
Date Normalization ← Converts to YYYY-MM-DD
    ↓
Date Validation ← Checks issued ≤ today, expiry ≥ today
    ↓
Issue Detection ← Flags missing/low-confidence fields
    ↓
JSON Output ← Ready for Part B (validation + RAG)
```

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Azure
1. Copy `.env.example` to `.env`
2. Replace with your actual connected Azure keys.

## Usage

### 🛠️ Single File Mode (Default)
Run extraction on a single certificate:
```bash
python main.py --file data/sample_certificate.txt
```

### 🚀 Batch Processing Mode (Phase 2)
Process a list of files defined in a CSV:
```bash
python batch_processor.py --csv data/batch_test.csv
```
*Output saved to `batch_results.json`*

## Testing

### Test 1: Valid Certificate
```bash
python main.py --file data/sample_certificate.txt
```

### Test 2: Expired Certificate  
```bash
python main.py --file data/sample_expired_cert.txt
```

### Test 3: Unit Tests
```bash
python tests/test_suite.py
```

## Output Format
```json
{
  "doc_id": "filename",
  "fields": {
    "issuer": "Global Tech Institute",
    "certificate_number": "GTI-2024-88A",
    "issued_date": "2024-03-10",
    "expiry_date": "2027-03-10",
    "subject": "Advanced Python Systems Engineering"
  },
  "confidence": { ... },
  "confidence_flags": []
}
```

## Implementation Notes
See [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) for detailed design decisions and trade-offs.
