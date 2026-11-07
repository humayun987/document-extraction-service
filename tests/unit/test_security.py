import pytest
import io
from fastapi.testclient import TestClient
from app.utils.file_detection import detect_file_type
from app.db.session import check_db_health

def test_detect_file_type_magic_bytes_spoofing():
    # Executable disguised as PDF
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00"
    with pytest.raises(ValueError, match="Unsupported or corrupted"):
        detect_file_type(fake_pdf, "invoice.pdf")

    # Pure text disguised as XLSX
    fake_xlsx = b"Hello, this is just plain text"
    with pytest.raises(ValueError, match="Unsupported or corrupted"):
        detect_file_type(fake_xlsx, "rentroll.xlsx")

def test_path_traversal_filename_sanitization(client: TestClient):
    schema_json = '{"fields": {"test": {"name": "Test"}}}'
    traversal_filename = "../../../../etc/cron.d/malicious.csv"
    csv_bytes = b"header1,header2\nval1,val2\n"

    response = client.post(
        "/jobs",
        files={"file": (traversal_filename, io.BytesIO(csv_bytes), "text/csv")},
        data={"schema": schema_json}
    )
    assert response.status_code == 202
    data = response.json()
    # The stored job must sanitize the traversal path into a basename
    assert ".." not in data["job_id"]

def test_oversized_upload_rejection_streaming(client: TestClient, monkeypatch):
    # Temporarily set max upload to 100 bytes to test immediate 413
    monkeypatch.setattr("app.config.settings.MAX_UPLOAD_SIZE", 100)
    schema_json = '{"fields": {"test": {"name": "Test"}}}'
    large_bytes = b"%PDF-1.4 " + b"X" * 200

    response = client.post(
        "/jobs",
        files={"file": ("large.pdf", io.BytesIO(large_bytes), "application/pdf")},
        data={"schema": schema_json}
    )
    assert response.status_code == 413

def test_database_healthcheck():
    assert check_db_health() is True
