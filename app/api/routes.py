import json
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Header, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from app.db.session import get_db
from app.api.dependencies import get_organization_id
from app.jobs.service import JobService
from app.config import settings
from app.utils.logging import logger

router = APIRouter()

@router.get("/health", summary="Liveness check")
def health():
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
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_SCHEMA", "message": f"Malformed schema JSON: {str(e)}"}
        )

    # 2. Read and validate file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "FILE_READ_ERROR", "message": f"Failed to read uploaded file: {str(e)}"}
        )

    if not content:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty"}
        )

    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": f"File size {len(content)} exceeds 50 MB limit"}
        )

    # 3. Create job
    try:
        job, is_existing = JobService.create_job(
            db=db,
            file_bytes=content,
            file_name=file.filename or "upload.bin",
            schema_dict=schema_dict,
            org_id=org_id,
            webhook_url=webhook_url
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

