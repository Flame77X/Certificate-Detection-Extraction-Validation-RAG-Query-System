# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Certificate Intelligence & Verification System: a Flask app plus CLI/batch tools that take a certificate file (PDF/image/txt), check whether it is a certificate, extract 5 fields (Azure OpenAI, or a free offline path: RapidOCR + rules), validate them, assign a final status, and store the result in ChromaDB for natural-language RAG queries.

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
OCR_PROVIDER=local EXTRACTION_PROVIDER=rules python backend/main.py --file backend/data/sample_scanned_cert.pdf  # force offline engines
python backend/scripts/make_sample_certs.py                   # regenerate synthetic image/PDF fixtures
```

- There is no linter or formatter configured.
- `requirements.lock` at the root is a UTF-16 `pip freeze` of a whole dev environment, not a curated lockfile. `backend/requirements.txt` is the source of truth.
- `backend/app.py` cannot be imported as `app`, because the `backend/app/` package shadows it. Tests load it with `importlib.util.spec_from_file_location` (see `TestFlaskAPI`).

## Environment

`.env` is loaded by `batch_processor.py` (`app.py` and `main.py` get it by importing that module). `app/llm_client.py` reads env vars at call time and is the only place that builds LLM clients. `get_client()` returns the Azure client, which is the only one that can do vision OCR and Azure embeddings. `get_chat_backend()` returns a `ChatBackend(client, model, provider)` for chat (extraction and RAG answers): Azure if configured, otherwise the first configured OpenAI-compatible provider in `AUTO_ORDER` (OpenRouter free models, custom `LLM_BASE_URL`, then Hugging Face router, which returns 402 for free accounts) using the plain `openai.OpenAI` client. Providers are declared in `OPENAI_COMPATIBLE`. All variables are documented in `.env.example`; the key ones are:
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_DEPLOYMENT`: one chat deployment used for extraction, vision OCR and RAG answers, so it must accept image input.
- `AZURE_EMBEDDING_DEPLOYMENT`
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `google/gemma-4-31b-it:free`), `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` (custom OpenAI-compatible), `HF_TOKEN`, `HF_MODEL`, `LLM_PROVIDER` (`auto`|`azure`|`openrouter`|`custom`|`huggingface`; auto order Azure > OpenRouter > custom > Hugging Face)
- `OCR_PROVIDER` (`auto`|`azure`|`local`), `EXTRACTION_PROVIDER` (`auto`|`llm`|`rules`)
- `USE_MOCK_LLM`, `EXTRACTION_ATTEMPTS`, `EXTRACTION_TEMPERATURE`, `FLASK_DEBUG`, `PORT`

A key that is missing or contains "your-key" counts as "not configured". In that state, with the `auto` defaults, OCR uses local RapidOCR and extraction uses `app/rule_extraction.py` (or fixed mock data if `USE_MOCK_LLM=1`). RAG uses local all-MiniLM-L6-v2 embeddings (ChromaDB's ONNX default, downloaded to `~/.cache/chroma` on first use) in a separate `certificates_local` collection, and `/query` returns extractive answers (closest records) instead of LLM text. If a provider key is set (`OPENROUTER_API_KEY`, `LLM_*` or `HF_TOKEN`), extraction and chat answers use that model instead of rules and extractive answers, while OCR and embeddings stay local. Every result carries `extraction_method` (`<provider>_consensus` (e.g. `openrouter_consensus`), `rules` or `mock`). If every LLM extraction run fails (for example HF 402 when credits are exhausted, or 429), extraction falls back to rules. If a chat call fails, `answer_question` falls back to `_extractive_answer` with the HTTP status in the header.

## Pipeline architecture

`process_single_file()` in `backend/batch_processor.py` is the single pipeline. `app.py` (`POST /upload`), `main.py` and the batch runner all call it.

1. `ocr_module.extract_text_from_file`: runs `security.validate_secure_path` (the file must resolve inside `backend/data/`) and `check_file_size` (10 MB). Then txt is read directly and PDFs go through `pypdf`. A PDF with fewer than 50 characters of text is treated as scanned: its embedded page images (first 3 pages) go to vision OCR. Images go straight to OCR. `ocr_image` routes by `OCR_PROVIDER`: Azure GPT vision, or local RapidOCR (PaddleOCR ONNX models, CPU, lazily loaded). `auto` falls back to local when Azure returns empty text.
2. `certificate_identification.is_certificate(ext, text)`: keyword/heuristic classifier. If it returns false, the pipeline returns `None`, which `/upload` turns into a 400.
3. `field_extraction.extract_with_azure`: self-consistency step. It runs `EXTRACTION_ATTEMPTS` (default 3) calls to `_extract_single` in parallel, using JSON mode (with a fallback for deployments that reject `response_format`) and input capped at 12k characters. `calculate_consensus` takes a majority vote per field, ignoring case and whitespace. **Confidence = winning votes / total attempts.** A null winner means the runs agreed the field is absent, and it scores the same way. Failed runs lower the confidence. The output is `{field: {value, confidence}}` plus `_voting_debug` and `_method`. Without Azure, `rule_extraction.extract_with_rules` reads labelled values ("Issued By:", "Valid Until:", "Ref.No.", "Date:", ...). For the subject it uses the "has completed the" phrasing or "thesis/project titled ...". For letters it falls back to an organisation-like letterhead line (first 8 lines) as the issuer. Its confidences are 0.75 / 0.6, deliberately below the 0.80 flag threshold, so rules-based results are always flagged.
4. `extract_fields` flattens that into `fields` / `confidence` and normalises dates to `YYYY-MM-DD`.
5. `date_validation.validate_dates` checks consistency, that the issued date is not in the future, and expiry. A missing expiry date gives `expiry_status: no_expiry`, which is not an error. `expiry_date` is in `logging_utils.OPTIONAL_FIELDS`. `validate_issuer` checks against `backend/trusted_issuers.json` after normalising (casefold, punctuation, legal suffixes such as "Pvt Ltd") with a strict `SequenceMatcher` threshold of 0.92. It returns `matched_issuer` and `match_score`.
6. `logging_utils.check_for_issues` raises `MISSING_<F>` and `LOW_CONFIDENCE_<F>` (below 0.80) flags. `log_extraction` appends PII-redacted JSONL to `backend/extraction_logs.json`.
7. `status_assignment.assign_certificate_status` applies its checks in a fixed order: average confidence < 0.7 gives Manual Review Required, then untrusted issuer gives Untrusted Issuer, then Expired, then missing critical fields gives Manual Review, then an invalid issued date gives Verification Failed, otherwise Verified.
8. `external_verification.verify_external_issuer(issuer, fields, text)` runs only for untrusted issuers. It finds verification URLs in the OCR text, fetches only HTTPS URLs on `ALLOWED_HOSTS` (badge platforms: Credly, Accredible, Badgr, ...) with a timeout, a size cap and allowlist-checked redirects, and parses the Open Badges 2.0 assertion. Credly badge pages are mapped to `api.credly.com/v1/obi/v2/badge_assertions/<id>`. The result is `Verified (Open Badges)`, `Failed (Revoked|Expired|Issuer mismatch)`, or `Manual Verification Required` (with `verification_url`). Callers match on the substrings "Verified" and "Manual". It does not prove the recipient, because OB2 recipients are hashed emails.
9. In `app.py` only, the result is upserted into ChromaDB with `doc_id` = the sanitised filename stem, so re-uploading the same name overwrites the earlier entry.

The output JSON contract (`create_json_output` plus `validation`, `issuer_validation`, `external_verification`, `final_status`) is rendered by the inline JS in `frontend/templates/index.html`. That JS must escape every model or extracted value with `escapeHtml` / `renderAnswer`.

## RAG

- `app/rag_pipeline.py`: `chromadb.PersistentClient` at `backend/data/chroma_db` (gitignored; the constructor takes `db_path` for tests), collection `certificates`, cosine distance.
- `RAG_EMBEDDINGS=auto|azure|local` picks Azure (collection `certificates`, 1536-dim) or local MiniLM (collection `certificates_local`, 384-dim). The two must never share a collection. Offline answers come from `_extractive_answer`, which keeps records within `LOCAL_MAX_DISTANCE` and within `LOCAL_DISTANCE_MARGIN` of the best match.
- Each certificate is stored as a summary record (id = `doc_id`, `kind: summary`, the extracted fields) plus the full OCR text split by `chunk_text` (~800 chars, 150 overlap) into `doc_id::chunk<i>` records (`kind: text`). All of them carry `doc_id` metadata. `app.py` gets the text via `process_single_file(path, include_text=True)`. The text is never put in the API response or `batch_results.json`. Re-ingesting deletes the old chunks (`delete(where={doc_id})`). `list_certificates` and Settings skip text chunks. With `doc_id`, `query` searches only that document's records. Records indexed before this change have no text and need re-uploading.
- `get_embeddings` returns `None` when embeddings are unavailable. Ingestion then skips the certificate and returns `success: False`, and queries return no sources. Placeholder vectors are never stored.
- `POST /query {question}` calls `answer_question`, which returns `{answer, sources: [{doc_id, issuer, status, distance}]}`. The prompt includes today's date (for expiry questions) and asks for `[doc_id]` citations, with temperature 0.

## Gotchas

- **Never commit real certificates.** `.gitignore` ignores everything in `backend/data/` except `sample_*` and `batch_test.csv`. Fixtures are fictional and generated by `backend/scripts/make_sample_certs.py`. Logs, `batch_results.json`, `chroma_db/` and uploads are ignored too.
- Changing the meaning of confidence affects two thresholds together: 0.80 for flags in `logging_utils` and 0.7 average for status in `status_assignment`.
- The root `*.md` files (security audits, viva prep, demo walkthrough, training strategy) are assignment write-ups that are not kept in sync with the code. Treat the code as the source of truth.
