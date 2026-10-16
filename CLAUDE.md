# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Certificate Intelligence & Verification System: a Flask app plus CLI/batch tools that take a certificate file (PDF/image/txt), check whether it is a certificate, extract 5 fields with Azure OpenAI, validate them, assign a final status, and store the result in ChromaDB for natural-language RAG queries.

## Commands

Run everything from `backend/`. Several paths are resolved relative to the current working directory (see "CWD-sensitive paths" below), so running from the repo root silently breaks file validation and writes logs to the wrong place.

```bash
cd backend
pip install -r requirements.txt flask chromadb requests   # requirements.txt only lists openai, python-dotenv, pypdf
python app.py                                  # Flask UI + API on http://localhost:5000
python main.py --file data/sample_certificate.txt          # single-file CLI
python batch_processor.py --csv data/batch_test.csv        # batch (flag is --csv, not --input as README says)
python tests/test_suite.py                     # unit tests (unittest)
python -m unittest tests.test_suite.TestCertificateSystem.test_date_validation   # single test
python test_rag.py                             # RAG smoke test (needs Azure keys)
python test_ai_connection.py                   # hits /query on a running server
```

- `requirements.lock` at the root is a UTF-16 `pip freeze` of a whole environment, not a curated lockfile.
- There is no linter or formatter configured.

## Environment

`.env` is loaded through `python-dotenv` in `main.py` / `batch_processor.py` (`app.py` gets it by importing `batch_processor`). Variables the code actually reads:
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION` (default `2024-02-15-preview`)
- `AZURE_OPENAI_DEPLOYMENT` (default `gpt-4`): used for extraction, vision OCR and RAG answers. The README calls it `AZURE_OPENAI_DEPLOYMENT_NAME`, which is wrong.
- `AZURE_EMBEDDING_DEPLOYMENT` (default `text-embedding-ada-002`)

The `AZURE_VISION_*` / `AZURE_DOCUMENT_INTELLIGENCE_*` variables in the README and `.env.example` are not read anywhere. OCR for images and scanned PDFs uses GPT-4 vision through the same Azure OpenAI client (`app/ocr_module.py`).

## Pipeline architecture

The canonical pipeline is `process_single_file()` in `backend/batch_processor.py`. `app.py` (`POST /upload`) calls it directly. `main.py` keeps its own copy of the same steps, so a change to the pipeline must be made in both places.

1. `ocr_module.extract_text_from_file`: calls `security.validate_secure_path` and `check_file_size` first. Then txt is read directly, PDFs go through `pypdf`, and images or PDFs with no text go to GPT-4 vision.
2. `certificate_identification.is_certificate(ext, text)`: keyword/heuristic classifier. If it returns false, the pipeline returns `None`, which `/upload` turns into a 400.
3. `field_extraction.extract_with_azure`: self-consistency step that calls `_extract_single` 3 times and takes a majority vote per field (`calculate_consensus`). It returns `{field: {value, confidence}}` plus a `_voting_debug` key. **If no real key is configured (missing, or containing "your-key"), `_extract_single` returns hard-coded mock ISO data**, so tests and demos run offline but return fake extractions.
4. `extract_fields` flattens the result into `fields` / `confidence` dicts and normalises dates to `YYYY-MM-DD` (`normalize_date`).
5. `date_validation.validate_dates` checks issued < expiry, that the issued date is not in the future, and the expiry status. `validate_issuer` checks against `backend/trusted_issuers.json`.
6. `logging_utils.check_for_issues` produces `LOW_CONFIDENCE_<FIELD>` (per-field confidence below 0.80) and `MISSING_<FIELD>` flags. `log_extraction` appends JSONL to `extraction_logs.json` after PII redaction (`security.redact_pii`).
7. `status_assignment.assign_certificate_status` applies its checks in a fixed order: average confidence < 0.7 gives Manual Review Required, then untrusted issuer gives Untrusted Issuer, then Expired, then missing critical fields gives Manual Review, then an invalid issued date gives Verification Failed, otherwise Verified.
8. "Task 7" `external_verification.verify_external_issuer` runs only when the issuer is untrusted. It is **simulated**: issuers matching a hard-coded registry (AWS/Microsoft/Coursera) with a cert number longer than 5 characters return "Verified (External API)", and no HTTP call is made. Its result can override `final_status`.
9. In `app.py` only, the output is upserted into ChromaDB (`rag_pipeline.CertificateRAG.ingest_certificate`) with `doc_id` = the filename stem as the vector ID, so re-uploading a file with the same name overwrites the earlier entry.

The output JSON contract (`create_json_output` plus `validation`, `issuer_validation`, `external_verification`, `final_status`) is what `frontend/templates/index.html` renders. Keep these keys stable or update the inline JS in that template.

## RAG

- `app/rag_pipeline.py`: `chromadb.PersistentClient` at `backend/data/chroma_db` (anchored to the module file, so it does not depend on the CWD), collection `certificates`, cosine distance. The DB files are committed to git.
- Without a key, embeddings fall back to a constant `[0.1]*1536` vector, and to `[0.0]*1536` on embedding errors. Retrieval is meaningless in both cases, but nothing raises.
- `POST /query {question}` calls `answer_question`, which retrieves the top 3 documents and asks GPT-4 to answer from them.

## CWD-sensitive paths

- `security.ALLOWED_DATA_DIR = os.path.abspath('data')` is evaluated at import time. Every processed file must sit under `<cwd>/data`, otherwise `validate_secure_path` raises `PermissionError`. This is why the server must be started from `backend/`.
- `app.py` saves uploads to `data/uploads` (relative to the CWD) using the raw `file.filename`. `secure_filename` is not used, although the README claims it is.
- `logging_utils.LOG_FILE = 'extraction_logs.json'` is relative to the CWD. This explains the stray copies at the repo root (`extraction_logs.json`, `batch_results.json`) next to `backend/extraction_logs.json`.
- The size limit is `MAX_FILE_SIZE_MB = 10` and the batch cap is `MAX_BATCH_SIZE = 50`, both in `app/security.py`. The README's "50 MB in app.py" is wrong.

## Tests

`backend/tests/test_suite.py` covers only the pure functions (identification, date validation, date normalisation, issue flags), and it puts `backend/` on `sys.path` itself. It does not exercise Flask, OCR, Azure or RAG. `test_rag.py` and `test_ai_connection.py` are manual scripts, not unittest cases.

## Docs

The root `*.md` files (security audits, viva prep, demo walkthrough, training strategy) are project/assignment write-ups and are not kept in sync with the code. Treat the code as the source of truth when they disagree.
