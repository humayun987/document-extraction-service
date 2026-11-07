import json
import pytest

SAMPLE_SCHEMA = {
    "name": "test_schema",
    "fields": {
        "property_name": {"name": "Property Name", "description": "The name of the property"},
        "rent": {"name": "Rent", "description": "Monthly rent amount"}
    }
}

SAMPLE_CSV = b"Code,Name,Rent\nUnit1,One,1500\nUnit2,Two,2000\n"

def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data

def test_post_jobs_success(client):
    files = {"file": ("test.csv", SAMPLE_CSV, "text/csv")}
    data = {"schema": json.dumps(SAMPLE_SCHEMA)}
    resp = client.post("/jobs", files=files, data=data)
    assert resp.status_code == 202
    res_json = resp.json()
    assert "job_id" in res_json
    assert res_json["status"] == "PENDING"
    assert res_json["stage"] == "QUEUED"
    assert "created_at" in res_json

def test_post_jobs_missing_file(client):
    data = {"schema": json.dumps(SAMPLE_SCHEMA)}
    resp = client.post("/jobs", data=data)
    assert resp.status_code in {400, 422}

def test_post_jobs_missing_schema(client):
    files = {"file": ("test.csv", SAMPLE_CSV, "text/csv")}
    resp = client.post("/jobs", files=files)
    assert resp.status_code in {400, 422}

def test_post_jobs_invalid_schema_json(client):
    files = {"file": ("test.csv", SAMPLE_CSV, "text/csv")}
    data = {"schema": "{invalid_json: true"}
    resp = client.post("/jobs", files=files, data=data)
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_SCHEMA"

def test_post_jobs_idempotency(client):
    files1 = {"file": ("test.csv", SAMPLE_CSV, "text/csv")}
    data1 = {"schema": json.dumps(SAMPLE_SCHEMA)}
    resp1 = client.post("/jobs", files=files1, data=data1, headers={"X-Organization-Id": "tenant-1"})
    assert resp1.status_code == 202
    job_id_1 = resp1.json()["job_id"]

    files2 = {"file": ("test.csv", SAMPLE_CSV, "text/csv")}
    data2 = {"schema": json.dumps(SAMPLE_SCHEMA)}
    resp2 = client.post("/jobs", files=files2, data=data2, headers={"X-Organization-Id": "tenant-1"})
    assert resp2.status_code == 202
    job_id_2 = resp2.json()["job_id"]

    assert job_id_1 == job_id_2

def test_tenant_isolation(client):
    files = {"file": ("test_tenant.csv", b"Code,Rent\n1,100\n", "text/csv")}
    data = {"schema": json.dumps(SAMPLE_SCHEMA)}
    
    # Create under Org A
    resp_a = client.post("/jobs", files=files, data=data, headers={"X-Organization-Id": "org-alpha"})
    assert resp_a.status_code == 202
    job_id = resp_a.json()["job_id"]

    # Retrieve under Org A -> 200
    get_a = client.get(f"/jobs/{job_id}", headers={"X-Organization-Id": "org-alpha"})
    assert get_a.status_code == 200
    assert get_a.json()["job_id"] == job_id

    # Retrieve under Org B -> 404 (Contract requirement: must not leak tenant jobs, returns 404 not 403)
    get_b = client.get(f"/jobs/{job_id}", headers={"X-Organization-Id": "org-beta"})
    assert get_b.status_code == 404
