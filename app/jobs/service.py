import uuid
import json
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.db.models import Job
from app.jobs.state_machine import JobStatus, JobStage, is_terminal, validate_transition
from app.utils.hashing import hash_bytes, hash_schema, generate_idempotency_key
from app.utils.file_detection import detect_file_type
from app.utils.logging import logger

def deliver_webhook(webhook_url: str, payload: Dict[str, Any], max_retries: int = 3):
    """Deliver webhook asynchronously with bounded backoff. Covers SUCCESS, PARTIAL, and FAILED."""
    if not webhook_url:
        return
    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(webhook_url, json=payload)
                if resp.status_code in {200, 201, 202, 204}:
                    logger.info(f"Webhook delivered successfully to {webhook_url}")
                    return
                elif resp.status_code == 429 or resp.status_code >= 500:
                    logger.warning(f"Webhook transient error {resp.status_code} on attempt {attempt}")
                else:
                    logger.warning(f"Webhook permanent error {resp.status_code} on attempt {attempt}")
                    return
        except Exception as e:
            logger.warning(f"Webhook connection failure on attempt {attempt}: {e}")
        import time
        time.sleep(min(8.0, 2 ** attempt))

class JobService:
    @staticmethod
    def create_job(
        db: Session,
        file_bytes: bytes,
        file_name: str,
        schema_dict: Dict[str, Any],
        org_id: str,
        webhook_url: Optional[str] = None
    ) -> Tuple[Job, bool]:
        """
        Validate upload, calculate hashes, check idempotency with DB unique constraint,
        persist file to isolated job directory, and insert job.
        Returns (job, is_existing).
        """
        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise ValueError(f"File size {len(file_bytes)} exceeds maximum limit of {settings.MAX_UPLOAD_SIZE} bytes")
            
        file_type = detect_file_type(file_bytes, file_name)
        file_hash = hash_bytes(file_bytes)
        schema_hash = hash_schema(schema_dict)
        idempotency_key = generate_idempotency_key(org_id, file_hash, schema_hash)
        
        # Fast query for idempotency
        existing_job = db.query(Job).filter(
            Job.organization_id == org_id,
            Job.idempotency_key == idempotency_key
        ).first()
        
        if existing_job:
            logger.info(
                f"Idempotent submission detected for existing job {existing_job.job_id}",
                extra={"job_id": existing_job.job_id, "organization_id": org_id}
            )
            return existing_job, True
            
        job_id = str(uuid.uuid4())
        job_dir = settings.STORAGE_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Use sanitized filename inside unique job directory
        file_path = job_dir / file_name
        file_path.write_bytes(file_bytes)
        
        now = datetime.now(timezone.utc)
        new_job = Job(
            job_id=job_id,
            organization_id=org_id,
            idempotency_key=idempotency_key,
            status=JobStatus.PENDING,
            stage=JobStage.QUEUED,
            created_at=now,
            updated_at=now,
            file_path=str(file_path),
            file_name=file_name,
            file_type=file_type,
            file_size=len(file_bytes),
            file_hash=file_hash,
            schema_hash=schema_hash,
            schema_name=schema_dict.get("name"),
            schema_data=schema_dict,
            webhook_url=webhook_url,
            retry_count=0,
            max_retries=3
        )
        
        try:
            db.add(new_job)
            db.commit()
            db.refresh(new_job)
            logger.info(
                f"Created job {job_id} for org {org_id} ({file_name}, {file_type})",
                extra={"job_id": job_id, "organization_id": org_id, "file_type": file_type}
            )
            return new_job, False
        except IntegrityError:
            # Handles concurrent identical submissions gracefully via DB unique constraint
            db.rollback()
            existing = db.query(Job).filter(
                Job.organization_id == org_id,
                Job.idempotency_key == idempotency_key
            ).first()
            if existing:
                return existing, True
            raise

    @staticmethod
    def get_job(db: Session, job_id: str, org_id: str) -> Optional[Job]:
        """Fetch job ensuring tenant isolation. Returns None if wrong tenant or not found."""
        return db.query(Job).filter(
            Job.job_id == job_id,
            Job.organization_id == org_id
        ).first()

    @staticmethod
    def update_stage(db: Session, job_id: str, stage: str):
        """Update job stage."""
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job and not is_terminal(job.status):
            job.stage = stage
            job.updated_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def check_and_enforce_timeout(db: Session, job: Job) -> bool:
        """
        Check if job has exceeded MAX_DOCUMENT_PROCESSING_TIME (1800s) from created_at.
        If exceeded, transitions job to FAILED. Returns True if timed out.
        """
        if is_terminal(job.status):
            return False
            
        now = datetime.now(timezone.utc)
        created = job.created_at if job.created_at.tzinfo else job.created_at.replace(tzinfo=timezone.utc)
        elapsed = (now - created).total_seconds()
        if elapsed > settings.MAX_DOCUMENT_PROCESSING_TIME:
            logger.error(
                f"Job {job.job_id} exceeded maximum processing time of {settings.MAX_DOCUMENT_PROCESSING_TIME}s (elapsed: {elapsed:.1f}s). Timing out."
            )
            JobService.finalize_job(
                db=db,
                job_id=job.job_id,
                worker_id=job.worker_id or "system-timeout",
                status=JobStatus.FAILED,
                error={
                    "code": "PROCESSING_TIMEOUT",
                    "message": f"Processing exceeded absolute deadline of {settings.MAX_DOCUMENT_PROCESSING_TIME} seconds."
                }
            )
            return True
        return False

    @staticmethod
    def finalize_job(
        db: Session,
        job_id: str,
        worker_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Transition job to terminal status (SUCCESS, PARTIAL, FAILED).
        Guarantees terminal status immutability.
        Triggers webhook delivery for all terminal statuses.
        """
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return False
            
        if is_terminal(job.status):
            logger.warning(f"Attempted to finalize already terminal job {job_id} (status: {job.status})")
            return False
            
        # Verify worker lease hasn't been claimed by someone else (unless system-timeout)
        if worker_id != "system-timeout" and job.worker_id != worker_id and job.worker_id is not None:
            logger.error(f"Worker {worker_id} tried to finalize job {job_id} owned by {job.worker_id}")
            return False
            
        now = datetime.now(timezone.utc)
        job.status = status
        job.stage = JobStage.COMPLETED
        job.result = result
        job.error = error
        job.updated_at = now
        job.lease_expires_at = None
        
        db.commit()
        db.refresh(job)
        
        logger.info(
            f"Finalized job {job_id} with status {status}",
            extra={"job_id": job_id, "status": status}
        )
        
        # Trigger webhook for ALL terminal statuses: SUCCESS, PARTIAL, and FAILED
        if job.webhook_url:
            import threading
            payload = job.to_dict()
            threading.Thread(
                target=deliver_webhook,
                args=(job.webhook_url, payload),
                daemon=True
            ).start()
            
        return True
