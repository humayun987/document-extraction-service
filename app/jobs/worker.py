import os
import time
import signal
import threading
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, init_db
from app.jobs.queue import DurableQueue
from app.jobs.service import JobService
from app.jobs.state_machine import JobStatus, JobStage
from app.extractors.tables import extract_document
from app.extraction.document_extractor import DocumentExtractor
from app.config import settings
from app.utils.logging import logger

class Worker:
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.running = False
        self._active_job_id = None
        self._heartbeat_thread = None

    def start(self):
        """Main worker execution loop."""
        self.running = True
        logger.info(f"Worker {self.worker_id} started. Polling queue...")

        # Setup graceful signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        init_db()

        while self.running:
            try:
                db: Session = SessionLocal()
                try:
                    # Periodically reclaim expired / orphaned jobs
                    DurableQueue.reclaim_expired_jobs(db)

                    # Atomically claim eligible job
                    job = DurableQueue.claim_job(
                        db=db,
                        worker_id=self.worker_id,
                        lease_seconds=settings.WORKER_LEASE_SECONDS
                    )

                    if job:
                        self._process_claimed_job(db, job)
                    else:
                        time.sleep(settings.WORKER_POLL_INTERVAL)
                finally:
                    db.close()
            except Exception as e:
                logger.exception(f"Unexpected error in worker loop: {e}")
                time.sleep(2.0)

        logger.info(f"Worker {self.worker_id} shut down gracefully.")

    def _process_claimed_job(self, db: Session, job):
        """Process a single claimed extraction job."""
        job_id = job.job_id
        self._active_job_id = job_id
        logger.info(
            f"Worker {self.worker_id} processing job {job_id} (file: {job.file_name}, type: {job.file_type})",
            extra={"job_id": job_id, "worker_id": self.worker_id}
        )

        # Start lease heartbeat thread
        stop_heartbeat = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._run_heartbeat,
            args=(job_id, stop_heartbeat),
            daemon=True
        )
        self._heartbeat_thread.start()

        status = JobStatus.SUCCESS
        result_payload = None
        error_payload = None

        try:
            # Stage: PARSING
            JobService.update_stage(db, job_id, JobStage.PARSING)
            parsed_doc = extract_document(job.file_path, job.file_type)

            # Stage: EXTRACTING
            JobService.update_stage(db, job_id, JobStage.EXTRACTING)
            extractor = DocumentExtractor()
            result_payload = extractor.extract(parsed_doc, job.schema_data)

            # Stage: FINALIZING
            JobService.update_stage(db, job_id, JobStage.FINALIZING)
            status = JobStatus.SUCCESS

        except Exception as e:
            logger.exception(f"Extraction failed for job {job_id}: {e}")
            status = JobStatus.FAILED
            error_payload = {
                "code": "EXTRACTION_FAILURE",
                "message": str(e)
            }
        finally:
            stop_heartbeat.set()
            self._heartbeat_thread = None
            self._active_job_id = None

            # Finalize job state
            JobService.finalize_job(
                db=db,
                job_id=job_id,
                worker_id=self.worker_id,
                status=status,
                result=result_payload,
                error=error_payload
            )

    def _run_heartbeat(self, job_id: str, stop_event: threading.Event):
        """Periodically extend job lease while worker is actively running."""
        interval = max(5, settings.WORKER_LEASE_SECONDS // 3)
        while not stop_event.wait(timeout=interval):
            try:
                db = SessionLocal()
                try:
                    success = DurableQueue.renew_lease(
                        db=db,
                        job_id=job_id,
                        worker_id=self.worker_id,
                        lease_seconds=settings.WORKER_LEASE_SECONDS
                    )
                    if not success:
                        logger.warning(f"Failed to extend heartbeat for job {job_id}")
                        break
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Heartbeat renewal error for job {job_id}: {e}")

    def _handle_shutdown(self, signum, frame):
        logger.info(f"Worker {self.worker_id} received shutdown signal {signum}. Stopping...")
        self.running = False

def run_worker():
    worker = Worker()
    worker.start()

if __name__ == "__main__":
    run_worker()

