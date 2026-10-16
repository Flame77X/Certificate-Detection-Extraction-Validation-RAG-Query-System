# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Certificate Intelligence & Verification System: a Flask app plus CLI/batch tools that take a certificate file (PDF/image/txt), check whether it is a certificate, extract 5 fields with Azure OpenAI, validate them, assign a final status, and store the result in ChromaDB for natural-language RAG queries.

## Commands

Paths are anchored to `backend/` (see `app/security.py: BACKEND_DIR`), so commands work from the repo root or from `backend/`.

```bash
pip install -r backend/requirements.txt
python backend/app.py                                         # Flask UI + API on http://localhost:5000 (FLASK_DEBUG=1 for debug)
python backend/main.py --file backend/data/sample_certificate.txt
python backend/batch_processor.py --csv backend/data/batch_test.csv
cd backend && python -m unittest discover -s tests -p "test_*.py"            # all tests (Azure is mocked)
cd backend && python -m unittest tests.test_pipeline.TestConsensus           # one class
cd backend && python -m unittest tests.test_pipeline.TestFlaskAPI.test_query_requires_question  # one test
USE_MOCK_LLM=1 python backend/main.py                         # offline run with fixed mock extraction
```

- There is no linter or formatter configured.
- `requirements.lock` at the root is a UTF-16 `pip freeze` of a whole dev environment, not a curated lockfile. `backend/requirements.txt` is the source of truth.
- `backend/app.py` cannot be imported as `app`, because the `backend/app/` package shadows it. Tests load it with `importlib.util.spec_from_file_location` (see `TestFlaskAPI`).

## Environment

`.env` is loaded by `batch_processor.py` (`app.py` and `main.py` get it by importing that module). `app/llm_client.py` reads env vars at call time and is the only place that builds the `AzureOpenAI` client. All variables are documented in `.env.example`; the key ones are:
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_DEPLOYMENT`: one chat deployment used for extraction, vision OCR and RAG answers, so it must accept image input.
- `AZURE_EMBEDDING_DEPLOYMENT`
- `USE_MOCK_LLM`, `EXTRACTION_ATTEMPTS`, `EXTRACTION_TEMPERATURE`, `FLASK_DEBUG`, `PORT`

A key that is missing or contains "your-key" counts as "not configured". In that state, extraction returns `{}` (all fields null, so the status is Manual Review Required) unless `USE_MOCK_LLM=1`, vision OCR returns empty text, and the RAG store indexes nothing.

## Pipeline architecture

`process_single_file()` in `backend/batch_processor.py` is the single pipeline. `app.py` (`POST /upload`), `main.py` and the batch runner all call it.

1. `ocr_module.extract_text_from_file`: runs `security.validate_secure_path` (the file must resolve inside `backend/data/`) and `check_file_size` (10 MB). Then txt is read directly and PDFs go through `pypdf`. A PDF with fewer than 50 characters of text is treated as scanned: its embedded page images (first 3 pages) go to vision OCR. Images go straight to vision OCR.
2. `certificate_identification.is_certificate(ext, text)`: keyword/heuristic classifier. If it returns false, the pipeline returns `None`, which `/upload` turns into a 400.
3. `field_extraction.extract_with_azure`: self-consistency step. It runs `EXTRACTION_ATTEMPTS` (default 3) calls to `_extract_single` in parallel, using JSON mode (with a fallback for deployments that reject `response_format`) and input capped at 12k characters. `calculate_consensus` takes a majority vote per field, ignoring case and whitespace. **Confidence = winning votes / total attempts.** A null winner gets 0.0, and failed runs lower the confidence. The output is `{field: {value, confidence}}` plus `_voting_debug`.
4. `extract_fields` flattens that into `fields` / `confidence` and normalises dates to `YYYY-MM-DD`.
5. `date_validation.validate_dates` checks consistency, that the issued date is not in the future, and expiry. `validate_issuer` checks against `backend/trusted_issuers.json` after normalising (casefold, punctuation, legal suffixes such as "Pvt Ltd") with a strict `SequenceMatcher` threshold of 0.92. It returns `matched_issuer` and `match_score`.
6. `logging_utils.check_for_issues` raises `MISSING_<F>` and `LOW_CONFIDENCE_<F>` (below 0.80) flags. `log_extraction` appends PII-redacted JSONL to `backend/extraction_logs.json`.
7. `status_assignment.assign_certificate_status` applies its checks in a fixed order: average confidence < 0.7 gives Manual Review Required, then untrusted issuer gives Untrusted Issuer, then Expired, then missing critical fields gives Manual Review, then an invalid issued date gives Verification Failed, otherwise Verified.
8. `external_verification.verify_external_issuer` runs only for untrusted issuers and is **simulated**: an AWS/Microsoft/Coursera name match plus a cert number longer than 5 characters gives "Verified (External API)", and no HTTP call is made. It can override `final_status`.
9. In `app.py` only, the result is upserted into ChromaDB with `doc_id` = the sanitised filename stem, so re-uploading the same name overwrites the earlier entry.

The output JSON contract (`create_json_output` plus `validation`, `issuer_validation`, `external_verification`, `final_status`) is rendered by the inline JS in `frontend/templates/index.html`. That JS must escape every model or extracted value with `escapeHtml` / `renderAnswer`.

## RAG

- `app/rag_pipeline.py`: `chromadb.PersistentClient` at `backend/data/chroma_db` (gitignored; the constructor takes `db_path` for tests), collection `certificates`, cosine distance.
- `get_embeddings` returns `None` when embeddings are unavailable. Ingestion then skips the certificate and returns `success: False`, and queries return no sources. Placeholder vectors are never stored.
- `POST /query {question}` calls `answer_question`, which returns `{answer, sources: [{doc_id, issuer, status, distance}]}`. The prompt includes today's date (for expiry questions) and asks for `[doc_id]` citations, with temperature 0.

## Gotchas

- Generated files are gitignored and untracked: `extraction_logs.json`, `batch_results.json`, `backend/data/chroma_db/` and the uploads folders. The sample certificates in `backend/data/` are still tracked.
- Changing the meaning of confidence affects two thresholds together: 0.80 for flags in `logging_utils` and 0.7 average for status in `status_assignment`.
- The root `*.md` files (security audits, viva prep, demo walkthrough, training strategy) are assignment write-ups that are not kept in sync with the code. Treat the code as the source of truth.
