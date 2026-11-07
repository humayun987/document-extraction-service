# System Design — Outcome Document Extraction Service

**Target Role:** AI/ML Developer (`aiml`)  
**Candidate Roll No:** 230480  
**Candidate Name:** Humayun Ahmad  

## Executive Summary
This service provides an enterprise-ready, asynchronous, schema-driven document intelligence pipeline capable of extracting structured CRE data across PDFs (both digital and scanned), DOCX, XLSX, and CSV files under strict resource, budget, and concurrency limits.

---

## A. Architecture
The architecture cleanly decouples ingress handling from heavy extraction compute:
- **API Layer (FastAPI):** High-throughput, non-blocking ingestion on port 8080. Validates uploads, enforces tenant boundaries (`X-Organization-Id`), hashes content for idempotency, writes payloads to persistent volume storage, inserts job records into PostgreSQL, and immediately responds with `202 Accepted` within milliseconds.
- **Durable Queue & State Machine (PostgreSQL):** Uses row-level atomic locking (`SELECT ... FOR UPDATE SKIP LOCKED`) with worker heartbeat leases. Prevents duplicate claims, survives worker crashes through automatic lease expiry reclamation, and guarantees terminal status immutability.
- **Worker Pipeline:** Scalable stateless worker processes that pull claimed jobs, route files through format-specific extractors, perform schema decomposition, execute deterministic and LLM-assisted extraction, normalize types, run derived arithmetic, verify evidence citations, validate contract adherence, and deliver terminal webhook payloads.

---

## B. Extraction Approach
The extraction engine is strictly schema-driven and document-agnostic:
1. **File Type Detection:** Validates magic bytes (signatures) and extensions for PDF, DOCX, XLSX, and CSV.
2. **Digital & Scanned PDF:** PyMuPDF extracts text, vector structures, and layout coordinates. Scanned pages (absence of extractable text layer) trigger local Tesseract OCR with adaptive image preprocessing (deskewing, contrast normalization). High-complexity or ambiguous regions are routed selectively to vision models.
3. **Word Documents (DOCX):** Extracts hierarchical paragraphs, run formatting, native tables, and tab-delimited text blocks (which frequently represent schedules).
4. **Spreadsheets & CSV (XLSX, CSV):** Inspects all sheets, unmerges cell matrices, extracts formulas vs cached values, detects multi-row tabular blocks, and generates exact cell address citations (`Sheet1!A1`).
5. **Dynamic Schema Analysis:** Analyzes incoming field definitions, infers data types, detects primary keys for table-row matching, and isolates document-level vs row-level fields.

---

## C. Model Selection & Routing
Strict adherence to the permitted OpenRouter model whitelist:
- **Tier 1 (Fast / Inexpensive Text Extraction):** `google/gemini-3.8-flash` for high-volume structured reasoning, standard document summaries, and field parsing.
- **Tier 2 (Complex Text & Legal Reasoning):** `deepseek/deepseek-v3.2` for intricate lease clauses, cross-reference interpretation, and ambiguous contractual covenants.
- **Tier 3 (Vision & Multimodal):** `z-ai/glm-5.3-flash` and `google/gemini-3.8-flash` for scanned pages, handwritten annotations, and visual table reconciliation.
- **Tier 4 (Escalation):** Targeted verification passes with `google/gemini-3.1-pro-preview` or `anthropic/claude-sonnet-5.5` only when confidence scores fall below threshold on high-weight fields.

---

## D. Cost & Budget Optimization
- **Deterministic First:** Structured files (rent rolls, financial statements, box scores) are parsed deterministically wherever column layouts and formulas allow, reducing LLM calls to zero or minimal classification queries.
- **Selective Multi-modal:** Only relevant pages identified via keyword/anchor search or structural headers are submitted for vision processing; full-document visual dumps are prohibited.
- **Batching & Prompt Compression:** Related fields sharing source context are grouped into structured single-turn JSON prompts.
- **Configurable Hard Ceiling:** A strict budget guard halts non-essential LLM escalation as spend nears the target ceiling, preserving reserve for operational tasks.

---

## E. Accuracy & Self-Verification
- **Null Discipline:** If reliable evidence is absent, the pipeline returns `null` with empty citation and appropriate confidence, preventing punitive hallucination deductions.
- **Verbatim Evidence Citations:** Every non-null value requires an exact text extract and location prefix (`[Page N] ...` or `[Sheet!Cell] ...`).
- **Deterministic Calculations:** Computes RSF rates, term months, variance amounts/percentages, and charge rollups with Decimal precision rather than relying on LLM arithmetic.
- **Confidence Calibration:** High confidence is reserved for deterministic cell reads and unambiguous verbatim text; OCR and inferred clauses reflect appropriate uncertainty.

---

## F. Reliability & Concurrency
- Multiple workers run concurrently without lock contention via `SKIP LOCKED`.
- Resilient exponential backoff with jitter handles provider 429 rate limits and 5xx transient errors.
- Webhook dispatches use non-blocking bounded retries and do not stall worker queues.

---

## G. Known Tradeoffs & Future Roadmap
- *Current Focus:* Maximum precision, cost efficiency, and resilient queuing on standard relational infrastructure.
- *Next Iteration:* Distributed vector index caching for multi-thousand-page institutional portfolios, native WASM PDF rendering, and active learning feedback loops.
