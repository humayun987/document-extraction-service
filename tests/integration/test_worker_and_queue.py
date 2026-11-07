from datetime import datetime, timezone, timedelta
from app.jobs.queue import DurableQueue
from app.jobs.service import JobService
from app.jobs.state_machine import JobStatus, JobStage
from app.db.models import Job

def test_durable_queue_claim_and_recovery(db_session):
    schema = {"name": "test", "fields": {"code": {"primary": True}}}
    
    # 1. Create a job
    job, is_existing = JobService.create_job(
        db=db_session,
        file_bytes=b"code,val\nA,1\n",
        file_name="queue_test.csv",
        schema_dict=schema,
        org_id="test_org"
    )
    assert job.status == JobStatus.PENDING

    # 2. Worker 1 claims job
    claimed = DurableQueue.claim_job(db_session, worker_id="worker-1", lease_seconds=10)
    assert claimed is not None
    assert claimed.job_id == job.job_id
    assert claimed.status == JobStatus.RUNNING
    assert claimed.worker_id == "worker-1"

    # 3. Simulate Worker 1 crashing: expire the lease
    claimed.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    db_session.commit()

    # 4. Worker 2 claims the orphaned job
    recovered = DurableQueue.claim_job(db_session, worker_id="worker-2", lease_seconds=10)
    assert recovered is not None
    assert recovered.job_id == job.job_id
    assert recovered.worker_id == "worker-2"
    assert recovered.retry_count == 1

    # 5. Finalize job to SUCCESS
    success = JobService.finalize_job(
        db=db_session,
        job_id=recovered.job_id,
        worker_id="worker-2",
        status=JobStatus.SUCCESS,
        result={"entries": [{"code": {"value": "A", "citation": "A", "confidence": 1.0}}], "metadata": {"model_calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "latency_ms": 10}}
    )
    assert success is True

    # 6. Terminal status immutability: late Worker 1 cannot overwrite finalized job
    late_try = JobService.finalize_job(
        db=db_session,
        job_id=recovered.job_id,
        worker_id="worker-1",
        status=JobStatus.FAILED
    )
    assert late_try is False
    
    # Verify job remains SUCCESS
    refreshed = db_session.query(Job).filter(Job.job_id == job.job_id).first()
    assert refreshed.status == JobStatus.SUCCESS

def test_job_processing_timeout_enforcement(db_session):
    schema = {"name": "timeout_test", "fields": {"id": {"primary": True}}}
    job, _ = JobService.create_job(
        db=db_session,
        file_bytes=b"id,col\n1,val\n",
        file_name="timeout.csv",
        schema_dict=schema,
        org_id="test_org"
    )

    # Simulate job created 1,801 seconds ago (exceeding MAX_DOCUMENT_PROCESSING_TIME = 1800)
    job.created_at = datetime.now(timezone.utc) - timedelta(seconds=1805)
    db_session.commit()

    timed_out = JobService.check_and_enforce_timeout(db_session, job)
    assert timed_out is True

    refreshed = db_session.query(Job).filter(Job.job_id == job.job_id).first()
    assert refreshed.status == JobStatus.FAILED
    assert refreshed.error["code"] == "PROCESSING_TIMEOUT"

def test_idempotency_under_identical_submission(db_session):
    schema = {"name": "idemp_test", "fields": {"id": {"primary": True}}}
    file_bytes = b"id,val\n1,test\n"

    job1, is_existing1 = JobService.create_job(
        db=db_session,
        file_bytes=file_bytes,
        file_name="idemp.csv",
        schema_dict=schema,
        org_id="org-alpha"
    )
    assert is_existing1 is False

    job2, is_existing2 = JobService.create_job(
        db=db_session,
        file_bytes=file_bytes,
        file_name="idemp.csv",
        schema_dict=schema,
        org_id="org-alpha"
    )
    assert is_existing2 is True
    assert job1.job_id == job2.job_id

    # Cross-tenant must create distinct job
    job3, is_existing3 = JobService.create_job(
        db=db_session,
        file_bytes=file_bytes,
        file_name="idemp.csv",
        schema_dict=schema,
        org_id="org-beta"
    )
    assert is_existing3 is False
    assert job3.job_id != job1.job_id
