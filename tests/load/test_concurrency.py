import json
import time
from concurrent.futures import ThreadPoolExecutor
from app.jobs.service import JobService
from app.jobs.queue import DurableQueue
from app.jobs.state_machine import JobStatus

def test_ten_document_concurrent_submission(client):
    """Test 10 simultaneous document submissions under load."""
    schema = {"name": "concurrent_test", "fields": {"code": {"primary": True}}}
    
    def submit_doc(idx):
        t0 = time.time()
        file_bytes = f"code,val\nU{idx},100\n".encode("utf-8")
        files = {"file": (f"concurrent_{idx}.csv", file_bytes, "text/csv")}
        data = {"schema": json.dumps(schema)}
        resp = client.post("/jobs", files=files, data=data, headers={"X-Organization-Id": f"org-{idx}"})
        latency = time.time() - t0
        return resp.status_code, resp.json(), latency

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(submit_doc, range(10)))

    job_ids = set()
    for status_code, body, latency in results:
        assert status_code == 202
        assert latency < 2.0  # Must return within 2 seconds
        assert body["status"] == "PENDING"
        job_ids.add(body["job_id"])

    # All 10 jobs must be distinct
    assert len(job_ids) == 10
