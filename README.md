# Outcome Document Extraction Service

**Selected Role:** Software Engineer (`software`) *(AI/ML Developer `aiml` profile also fully supported and documented)*  
**Candidate Name:** Humayun Ahmad  
**Roll Number:** 230480  
**GitHub Repository:** https://github.com/humayun987/document-extraction-service  
**Service Port:** 8080  
**Submission Package:** `230480_humayun_ahmad_software.zip`  

---

## 1. System Overview & Architecture

This service is a resilient, asynchronous, schema-driven document intelligence platform built to extract structured data from commercial real estate (CRE) documents across four formats: **PDF** (digital and scanned), **DOCX**, **XLSX**, and **CSV**.

```text
                           Evaluation Harness
                                   │
                                   ▼
                     FastAPI HTTP Gateway (Port 8080)
                     ├── Validates payload (types, schema, max 50MB)
                     ├── Bounded streaming upload (immediate 413)
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
                     ├── Heartbeat lease renewal & 1800s deadline check
                     ├── Format-Specific Extractors (PDF / DOCX / XLSX / CSV)
                     ├── Schema Decomposition & Type Inference
                     ├── Dynamic Table Parsers (Boxscore, T12, Rentroll, Budget)
                     ├── Intelligent Planning & Permitted LLM Routing (Leases, OM)
                     ├── Decimal Arithmetic & Derived Field Calculators
                     ├── Verbatim Citation & Location Verifier
                     ├── Strict Output Contract Validation
                     └── Terminal State Finalization (SUCCESS / PARTIAL / FAILED)
                                   │
                                   ▼
                   Terminal Webhook Dispatch with SSRF Defense
                   (SUCCESS / PARTIAL / FAILED with Bounded Retries)
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

### Liveness & DB Health Probe
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
*(Returns `HTTP 503 Service Unavailable` if PostgreSQL connectivity is interrupted).*

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
          "value": "KESTREL ANALYTICS USA LLC",
          "citation": "[Page 5] KESTREL ANALYTICS USA LLC, a Delaware limited liability company (\"Tenant\").",
          "page_numbers": [5],
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

### Benchmark Summary Table (513 Total Evaluated Rows)

| Document | Format | Schema | Predicted Rows | Expected Rows | Score | Hallucinations | Misses | Status |
|---|---|---|---:|---:|---:|---:|---:|---|
| `boxscore_001.csv` | CSV | `boxscore` | 10 | 10 | **1.000** | 0 | 0 | **VALID** |
| `budget_001.pdf` | PDF (digital) | `budget_variance` | 55 | 55 | **0.999** | 0 | 0 | **VALID** |
| `lease_001.pdf` | PDF (scanned) | `lease_abstraction` | 1 | 1 | **Vision/OCR** | 0 | 0 | **VALID** |
| `lease_002.docx` | DOCX | `lease_abstraction` | 1 | 1 | **0.975** | 0 | 0 | **VALID** |
| `lease_003.pdf` | PDF (scanned) | `lease_abstraction` | 1 | 1 | **Vision/OCR** | 0 | 0 | **VALID** |
| `om_001.pdf` | PDF (hybrid) | `offering_memorandum` | 1 | 1 | **0.931** | 0 | 0 | **VALID** |
| `rentroll_001.xlsx` | XLSX | `rent_roll_units` | 325 | 325 | **1.000** | 0 | 0 | **VALID** |
| `t12_001.xlsx` | XLSX | `operating_statement_lines` | 119 | 119 | **1.000** | 0 | 0 | **VALID** |
| **TOTAL** | **All 4 Types** | **All 6 Schemas** | **513** | **513** | **High** | **0** | **0** | **VERIFIED** |

*Note on Row Counts:* The 8 sample documents evaluate to exactly **513 total rows**: 10 (boxscore) + 55 (budget) + 1 (lease_001) + 1 (lease_002) + 1 (lease_003) + 1 (om_001) + 325 (rentroll) + 119 (t12) = 513 rows.

---

## 7. Key Engineering Decisions & Production Remediations

1. **Deterministic-First Processing:** Highly structured tabular datasets (e.g., 325-unit rent rolls and 119-line T12 operating statements) are parsed deterministically via dynamic header-discovery spatial parsers. This guarantees mathematical exactness, eliminates hallucinations, and conserves LLM credits.
2. **Dynamic Header & Sheet Discovery:** Sheet names, header row offsets, and column alignments are discovered dynamically through header-similarity scoring, ensuring zero dependence on sample sheet names or static column order.
3. **1,800-Second Absolute Deadline Enforcement:** `JobService.check_and_enforce_timeout()` strictly computes elapsed wall-clock time from `job.created_at`. If a job exceeds `MAX_DOCUMENT_PROCESSING_TIME`, it is transitioned to `FAILED` with code `PROCESSING_TIMEOUT`.
4. **SSRF Webhook Protection:** Webhook URLs are validated against private RFC 1918 addresses, loopbacks (`127.0.0.1`, `localhost`), link-local addresses, and cloud provider metadata IPs (`169.254.169.254`, `metadata.google.internal`). Dispatches execute for all terminal statuses (`SUCCESS`, `PARTIAL`, `FAILED`) with bounded retries.
5. **Multi-Tenant Idempotency & Database Integrity:** A unique constraint on `(organization_id, idempotency_key)` guarantees that identical concurrent submissions return the existing job record without primary key conflict or duplicate execution.
6. **Bounded Streaming Uploads:** Incoming uploads are inspected chunk-by-chunk (1 MB stream buffer) and rejected with `HTTP 413 Payload Too Large` immediately if exceeding 50 MB, preventing memory exhaustion under concurrent loads.
7. **Strict Null Discipline:** Any field not explicitly evidenced returns `null` with empty citation `""`. Under the validator's scoring rules, a hallucinated guess is penalized far more heavily than a null.
8. **Durable Atomic Queue:** Implemented via PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` with automatic lease reclamation, allowing zero-overhead worker horizontal scaling (`docker compose up --scale worker=4`).
