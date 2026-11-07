import json
from pathlib import Path
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Header, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from app.db.session import get_db, check_db_health
from app.api.dependencies import get_organization_id
from app.jobs.service import JobService
from app.config import settings
from app.utils.logging import logger

router = APIRouter()

BLOCKED_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata",
    "instance-data"
}

def validate_webhook_url(url: Optional[str]) -> Optional[str]:
    """Validate webhook URL scheme and guard against SSRF against cloud metadata services."""
    if not url:
        return None
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_WEBHOOK", "message": "Webhook URL must use http or https scheme"}
        )
    hostname = (parsed.hostname or "").lower()
    if hostname in BLOCKED_HOSTS or hostname.startswith("169.254."):
        raise HTTPException(
            status_code=400,
            detail={"code": "FORBIDDEN_WEBHOOK", "message": "Webhook destination is not permitted"}
        )
    return url

@router.get("/health", summary="Liveness check")
def health():
    db_ok = check_db_health()
    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Database connectivity check failed"}
        )
    return {"status": "ok", "version": "1.0.0"}

@router.post("/jobs", status_code=202, summary="Submit a document for extraction")
async def create_job(
    file: UploadFile = File(..., description="Document file: PDF, DOCX, XLSX, CSV up to 50MB"),
    schema: str = Form(..., description="Schema JSON as a string"),
    webhook_url: Optional[str] = Form(None, description="Optional webhook URL"),
    org_id: str = Depends(get_organization_id),
    db: Session = Depends(get_db)
):
    # 1. Validate schema JSON
    if not schema or not schema.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_SCHEMA", "message": "Schema form field is required"}
        )
    try:
        schema_dict = json.loads(schema)
        if not isinstance(schema_dict, dict) or "fields" not in schema_dict:
            raise ValueError("Schema must be a JSON object containing a 'fields' map")
        if not isinstance(schema_dict["fields"], dict) or not schema_dict["fields"]:
            raise ValueError("Schema 'fields' must be a non-empty JSON object")
        for f_key, f_val in schema_dict["fields"].items():
            if not isinstance(f_val, dict):
                raise ValueError(f"Field '{f_key}' must have an object definition")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_SCHEMA", "message": f"Malformed schema JSON: {str(e)}"}
        )

    # 2. Validate webhook URL if provided
    valid_webhook = validate_webhook_url(webhook_url)

    # 3. Read and validate file content with bounded chunk streaming
    chunk_size = 1024 * 1024  # 1MB chunks
    total_size = 0
    chunks = []
    
    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail={"code": "FILE_TOO_LARGE", "message": f"File size exceeds 50 MB limit"}
                )
            chunks.append(chunk)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "FILE_READ_ERROR", "message": f"Failed to read uploaded file: {str(e)}"}
        )

    content = b"".join(chunks)
    if not content:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty"}
        )

    # 4. Sanitize client filename
    raw_filename = file.filename or "upload.bin"
    safe_filename = Path(raw_filename).name  # strips directory traversal components
    if not safe_filename or safe_filename in {".", ".."}:
        safe_filename = "upload.bin"

    # 5. Create job
    try:
        job, is_existing = JobService.create_job(
            db=db,
            file_bytes=content,
            file_name=safe_filename,
            schema_dict=schema_dict,
            org_id=org_id,
            webhook_url=valid_webhook
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_FILE", "message": str(ve)}
        )
    except Exception as e:
        logger.exception("Unexpected error during job creation")
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )

    return JSONResponse(status_code=202, content=job.to_dict())

@router.get("/jobs/{job_id}", summary="Get job status and result")
def get_job(
    job_id: str,
    org_id: str = Depends(get_organization_id),
    db: Session = Depends(get_db)
):
    job = JobService.get_job(db=db, job_id=job_id, org_id=org_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Job {job_id} not found"}
        )
    return job.to_dict()
