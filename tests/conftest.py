import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///./test_extraction.db"
os.environ["LLM_BASE_URL"] = "https://mock-openrouter.ai/api/v1"
os.environ["LLM_API_KEY"] = "mock-key-for-tests"

from app.main import app
from app.db.models import Base, Job
from app.db.session import engine, SessionLocal, get_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    db_file = Path("./test_extraction.db")
    if db_file.exists():
        try:
            db_file.unlink()
        except Exception:
            pass

@pytest.fixture(autouse=True)
def clean_db():
    db = SessionLocal()
    try:
        db.query(Job).delete()
        db.commit()
    finally:
        db.close()
    yield

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
