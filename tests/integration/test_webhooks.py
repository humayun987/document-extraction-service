import pytest
from unittest.mock import patch, MagicMock
from app.jobs.service import deliver_webhook, JobService
from app.jobs.state_machine import JobStatus
from app.api.routes import validate_webhook_url
from fastapi import HTTPException

def test_webhook_ssrf_blocking():
    # Loopback and cloud metadata URLs must be rejected
    with pytest.raises(HTTPException) as exc:
        validate_webhook_url("http://169.254.169.254/latest/meta-data")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        validate_webhook_url("http://metadata.google.internal/computeMetadata/v1/")
    assert exc.value.status_code == 400

    # Non-http/https scheme must be rejected
    with pytest.raises(HTTPException) as exc:
        validate_webhook_url("ftp://example.com/callback")
    assert exc.value.status_code == 400

    # Legitimate webhook URL must be accepted
    assert validate_webhook_url("https://client.example.com/webhook") == "https://client.example.com/webhook"

def test_webhook_delivery_success():
    payload = {"job_id": "test-123", "status": "SUCCESS"}
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        deliver_webhook("https://client.example.com/callback", payload)
        assert mock_post.called

def test_webhook_delivery_for_all_terminal_statuses(db_session):
    # Test that finalize_job triggers delivery for SUCCESS, PARTIAL, and FAILED
    from app.db.models import Job
    import datetime

    statuses = [JobStatus.SUCCESS, JobStatus.PARTIAL, JobStatus.FAILED]
    for status in statuses:
        job = Job(
            job_id=f"job-{status}",
            organization_id="test-org",
            status=JobStatus.RUNNING,
            file_path="dummy.pdf",
            file_name="dummy.pdf",
            file_type="pdf",
            file_size=100,
            file_hash="hash",
            schema_hash="shash",
            schema_data={"fields": {}},
            webhook_url="https://client.example.com/webhook",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db_session.add(job)
        db_session.commit()

        with patch("threading.Thread.start") as mock_thread_start:
            success = JobService.finalize_job(
                db=db_session,
                job_id=job.job_id,
                worker_id="worker-1",
                status=status
            )
            assert success is True
            assert mock_thread_start.called
