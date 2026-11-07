# Outcome Document Extraction Service

**Target Role:** AI/ML Developer (`aiml`)  
**Repository:** outcome-document-extraction  
**Service Port:** 8080  

## Overview
A production-grade, asynchronous document extraction service designed to extract structured information from complex commercial real estate (CRE) documents (PDF, DOCX, XLSX, CSV) against dynamic JSON schemas. Built with FastAPI, PostgreSQL durable job queue, multi-format parsers, evidence citation verifier, and cost-aware permitted LLM routing.

## Technology Stack
- **API Framework:** FastAPI, Uvicorn, Pydantic v2
- **Durable Queue & Persistence:** PostgreSQL, SQLAlchemy (2.0) with row locking (`FOR UPDATE SKIP LOCKED`)
- **Document Processing:** PyMuPDF (`fitz`), pdfplumber, python-docx, openpyxl, standard csv
- **OCR Engine:** Tesseract OCR, PyTesseract, OpenCV
- **Model Gateway:** OpenRouter OpenAI-compatible client with strict model whitelisting and budget tracking
- **Testing & Validation:** pytest, pytest-asyncio, contract validator (`tools/validate.py`)
- **Containerization:** Docker, Docker Compose

## Quickstart

### Running with Docker Compose
```bash
docker compose up --build
```
The service will start and listen on port `8080`.

Verify health check:
```bash
curl http://localhost:8080/health
```

### Environment Variables
- `LLM_BASE_URL`: OpenAI-compatible endpoint URL (e.g., `https://openrouter.ai/api/v1`)
- `LLM_API_KEY`: API authentication key
- `DATABASE_URL`: PostgreSQL connection string (defaults to containerized postgres in Docker Compose)
- `SERVICE_PORT`: Service listening port (default `8080`)
- `MAX_UPLOAD_SIZE`: 52428800 (50 MB)
- `STORAGE_DIR`: Persistent storage path for uploaded documents

## API Endpoints

### 1. `GET /health`
Liveness probe returning `200 OK` with service status.

### 2. `POST /jobs`
Multipart form upload accepting:
- `file`: Document file (PDF, DOCX, XLSX, CSV up to 50MB)
- `schema`: JSON string of target field schema
- `webhook_url` (optional): URL to POST terminal result
- Optional header: `X-Organization-Id` for tenant isolation

Returns `202 Accepted` with initial job status.

### 3. `GET /jobs/{job_id}`
Returns current job status (`PENDING`, `RUNNING`, `SUCCESS`, `PARTIAL`, `FAILED`). Terminal states are immutable and include the validated `result` object.

## Evaluation & Scoring
Detailed benchmark results across the sample evaluation suite validated against `tools/validate.py` will be documented here.
