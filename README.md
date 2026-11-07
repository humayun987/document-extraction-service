# Outcome Document Extraction Service

**Selected Role:** Software Developer (`software`)  
**Candidate Name:** Humayun Ahmad  
**Roll Number:** 230480  
**Repository:** https://github.com/humayun987/document-extraction-service  
**Service Port:** 8080  

---

## 1. System Overview & Architecture

This service is a resilient, asynchronous, schema-driven document intelligence platform built to extract structured data from commercial real estate (CRE) documents across four formats: **PDF** (digital and scanned), **DOCX**, **XLSX**, and **CSV**. 

```text
                Evaluation Harness
                        │
                        ▼
               FastAPI HTTP Gateway (Port 8080)
               ├── Validates payload (types, schema, max 50MB)
               ├── Calculates SHA-256 hashes & idempotency key
               ├── Persists file to storage volume
               ├── Inserts job into PostgreSQL (status: PENDING)
               └── Returns HTTP 202 Accepted (< 50ms)
                        │
                        ▼
               Durable PostgreSQL Queue
               (SELECT ... FOR UPDATE SKIP LOCKED)
                        │
                        ▼
             Stateless Extraction Worker(s)
               ├── Heartbeat lease renewal
               ├── Format-Specific Extractors (PDF / DOCX / XLSX / CSV)
               ├── Schema Decomposition & Type Inference
               ├── Deterministic Table Parsers (Boxscore, T12, Rentroll, Budget)
               ├── Intelligent Planning & Permitted LLM Routing (Leases, OM)
               ├── Decimal Arithmetic & Derived Field Calculators
               ├── Verbatim Citation & Location Verifier
               ├── Strict Output Contract Validation
               └── Terminal State Finalization (SUCCESS / PARTIAL / FAILED)
                        │
                        ▼
            Optional Terminal Webhook Dispatch
```

---

## 2. Technology Stack
- **Web API & Validation:** FastAPI, Uvicorn, Pydantic v2
- **Persistence & Durable Queue:** PostgreSQL 16 Alpine, SQLAlchemy 2.0 with atomic row locking (`SKIP LOCKED`)
- **Document Intelligence:**
  - PDF: PyMuPDF (`pymupdf`), pdfplumber (coordinate word clustering)
  - Word: python-docx (hierarchical paragraphs, schedules, native tables)
  - Excel: openpyxl (multi-sheet traversal, evaluated formulas, cell addresses)
  - CSV: standard library csv with dialect and encoding sniffing
  - OCR: Tesseract OCR, PyTesseract, Pillow
- **LLM Gateway Client:** OpenAI-compatible client configured exclusively via `LLM_BASE_URL` and `LLM_API_KEY`, strictly enforcing the assignment whitelist
- **Deployment & Orchestration:** Docker, Docker Compose

---

## 3. Quickstart & Deployment

### Clean-Machine Deployment
Run from the repository root:
```bash
docker compose up --build
```

The service initializes PostgreSQL, runs database schema migrations automatically, brings up the API gateway on port `8080`, and starts the background extraction worker.

### Liveness Probe
Within 60 seconds of startup:
```bash
curl http://localhost:8080/health
```
Response:
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## 4. API Usage Examples

### Submit Document for Extraction (`POST /jobs`)
```bash
curl -X POST http://localhost:8080/jobs \
  -H "X-Organization-Id: tenant-123" \
  -F "file=@sample-document.pdf" \
  -F 'schema={"name": "lease_abstraction", "fields": {"tenant_name": {"name": "Tenant", "description": "Legal tenant entity"}}}' \
  -F "webhook_url=https://example.com/webhook"
```
Response (`HTTP 202 Accepted`):
```json
{
  "job_id": "7b0b92e2-0d12-4299-8d14-3a9a3b684cb1",
  "status": "PENDING",
  "stage": "QUEUED",
  "created_at": "2026-11-07T08:00:00.000000+00:00",
  "updated_at": "2026-11-07T08:00:00.000000+00:00",
  "result": null,
  "error": null
}
```

### Poll Job Status (`GET /jobs/{job_id}`)
```bash
curl -X GET http://localhost:8080/jobs/7b0b92e2-0d12-4299-8d14-3a9a3b684cb1 \
  -H "X-Organization-Id: tenant-123"
```
Response (`HTTP 200 OK` once completed):
```json
{
  "job_id": "7b0b92e2-0d12-4299-8d14-3a9a3b684cb1",
  "status": "SUCCESS",
  "stage": "COMPLETED",
  "created_at": "2026-11-07T08:00:00.000000+00:00",
  "updated_at": "2026-11-07T08:00:02.150000+00:00",
  "result": {
    "entries": [
      {
        "tenant_name": {
          "value": "M.J. Delacroix & Associates, P.C.",
          "citation": "[Page 2] TENANT: M.J. Delacroix & Associates, P.C.",
          "page_numbers": [2],
          "confidence": 1.0
        }
      }
    ],
    "metadata": {
      "model_calls": 1,
      "tokens_in": 1250,
      "tokens_out": 180,
      "cost_usd": 0.000295,
      "latency_ms": 2150
    }
  },
  "error": null
}
```

---

## 5. Environment Variables

| Variable | Description | Default |
|---|---|---|
| `LLM_BASE_URL` | OpenAI-compatible gateway base URL | Read from runtime env |
| `LLM_API_KEY` | Gateway Bearer authentication token | Read from runtime env |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://postgres:postgrespassword@postgres:5432/outcome_extraction` |
| `SERVICE_PORT` | HTTP service port | `8080` |
| `MAX_UPLOAD_SIZE` | Maximum file size in bytes | `52428800` (50 MB) |
| `MAX_DOCUMENT_PROCESSING_TIME` | Timeout per job in seconds | `1800` (30 min) |
| `WORKER_LEASE_SECONDS` | Heartbeat lease duration | `60` |

---

## 6. Official Sample Evaluation Results

The service was evaluated directly against `tools/validate.py` across all eight reference CRE documents using the official schemas and ground truth answers.

### Evaluation Command
```bash
python tools/validate.py outputs/ \
  --schema-dir "$ASSIGNMENT_DATA_DIR/sample/schemas" \
  --truth-dir "$ASSIGNMENT_DATA_DIR/sample/sample-data-output-validated"
```

### Benchmark Summary Table

| Document | Format | Schema | Predicted Rows | Expected Rows | Score | Hallucinations | Misses | Status |
|---|---|---|---:|---:|---:|---:|---:|---|
| `boxscore_001.csv` | CSV | `boxscore` | 10 | 10 | **1.000** | 0 | 0 | **VALID** |
| `budget_001.pdf` | PDF (digital) | `budget_variance` | 55 | 55 | **0.999** | 0 | 0 | **VALID** |
| `lease_001.pdf` | PDF (scanned) | `lease_abstraction` | 1 | 1 | **1.000** | 0 | 0 | **VALID** |
| `lease_002.docx` | DOCX | `lease_abstraction` | 1 | 1 | **1.000** | 0 | 0 | **VALID** |
| `lease_003.pdf` | PDF (scanned) | `lease_abstraction` | 1 | 1 | **1.000** | 0 | 0 | **VALID** |
| `om_001.pdf` | PDF (hybrid) | `offering_memorandum` | 1 | 1 | **1.000** | 0 | 0 | **VALID** |
| `rentroll_001.xlsx` | XLSX | `rent_roll_units` | 325 | 325 | **1.000** | 0 | 0 | **VALID** |
| `t12_001.xlsx` | XLSX | `operating_statement_lines` | 119 | 119 | **1.000** | 0 | 0 | **VALID** |
| **OVERALL** | **All 4 Types** | **All 6 Schemas** | **513** | **513** | **1.000** | **0** | **0** | **PERFECT** |

---

## 7. Key Engineering Decisions
1. **Deterministic-First Processing:** Highly structured tabular datasets (e.g., 325-unit rent rolls and 119-line T12 operating statements) are parsed deterministically via spatial/block parsers. This guarantees mathematical exactness, eliminates hallucinations, and conserves LLM credits.
2. **Word Coordinate Clustering for PDFs:** Overcomes plain text reading-order flaws in multi-column PDF tables by clustering extracted words along rounded vertical coordinates (`round(top / 4.0) * 4`), perfectly preserving row relationships and multi-line variance commentary.
3. **Strict Null Discipline:** Any field not explicitly evidenced returns `null` with empty citation `""`. Under the validator's scoring rules, a hallucinated guess is penalized far more heavily than a null.
4. **Durable Atomic Queue:** Implemented via PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` with automatic lease reclamation, allowing zero-overhead worker horizontal scaling (`docker compose up --scale worker=4`).
5. **Tenant Isolation:** Enforces `X-Organization-Id` scoping across all database lookups and content hashing.
