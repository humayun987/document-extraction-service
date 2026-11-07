from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.db.models import Job
from app.jobs.state_machine import JobStatus, JobStage
from app.utils.logging import logger

class DurableQueue:
    @staticmethod
    def claim_job(db: Session, worker_id: str, lease_seconds: int = 60) -> Optional[Job]:
        """
        Atomically claim a pending or orphaned/expired running job using row-level locking.
        Uses SELECT ... FOR UPDATE SKIP LOCKED on PostgreSQL.
        """
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=lease_seconds)
        
        # Build query for eligible jobs
        query = db.query(Job).filter(
            or_(
                Job.status == JobStatus.PENDING,
                and_(
                    Job.status == JobStatus.RUNNING,
                    Job.lease_expires_at < now,
                    Job.retry_count < Job.max_retries
                )
            )
        ).order_by(Job.created_at.asc())
        
        # Apply row-level locking with SKIP LOCKED if supported (PostgreSQL)
        is_postgres = "postgresql" in str(db.bind.url) if db.bind else False
        if is_postgres:
            query = query.with_for_update(skip_locked=True)
            
        job = query.first()
        if not job:
            return None
            
        # If reclaiming an expired running job, increment retry count
        if job.status == JobStatus.RUNNING:
            job.retry_count += 1
            logger.warning(
                f"Reclaiming expired job {job.job_id} (retry {job.retry_count}/{job.max_retries}) from previous worker {job.worker_id}",
                extra={"job_id": job.job_id, "worker_id": worker_id}
            )
            
        job.status = JobStatus.RUNNING
        job.stage = JobStage.PARSING
        job.worker_id = worker_id
        job.lease_expires_at = lease_until
        job.updated_at = now
        
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def renew_lease(db: Session, job_id: str, worker_id: str, lease_seconds: int = 60) -> bool:
        """Extend heartbeat lease for currently active worker."""
        now = datetime.now(timezone.utc)
        job = db.query(Job).filter(
            Job.job_id == job_id,
            Job.worker_id == worker_id,
            Job.status == JobStatus.RUNNING
        ).first()
        
        if not job:
            return False
            
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.updated_at = now
        db.commit()
        return True

    @staticmethod
    def reclaim_expired_jobs(db: Session) -> int:
        """Mark permanently failed jobs that exceeded max retries upon lease expiry."""
        now = datetime.now(timezone.utc)
        expired_exhausted = db.query(Job).filter(
            Job.status == JobStatus.RUNNING,
            Job.lease_expires_at < now,
            Job.retry_count >= Job.max_retries
        ).all()
        
        count = 0
        for job in expired_exhausted:
            job.status = JobStatus.FAILED
            job.error = {"code": "WORKER_TIMEOUT", "message": "Job lease expired and max retries exhausted"}
            job.updated_at = now
            count += 1
            
        if count > 0:
            db.commit()
            logger.warning(f"Marked {count} exhausted jobs as FAILED")
        return count

