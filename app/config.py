import os
from pathlib import Path
from pydantic import BaseModel, Field

class Settings(BaseModel):
    SERVICE_PORT: int = Field(default_factory=lambda: int(os.getenv("SERVICE_PORT", "8080")))
    TARGET_ROLE: str = Field(default_factory=lambda: os.getenv("TARGET_ROLE", "aiml"))
    MAX_UPLOAD_SIZE: int = Field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_SIZE", str(50 * 1024 * 1024))))
    MAX_DOCUMENT_PROCESSING_TIME: int = Field(default_factory=lambda: int(os.getenv("MAX_DOCUMENT_PROCESSING_TIME", "1800")))
    EXPECTED_CONCURRENT_DOCUMENTS: int = Field(default_factory=lambda: int(os.getenv("EXPECTED_CONCURRENT_DOCUMENTS", "10")))
    
    # Database
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5432/outcome_extraction"
        )
    )
    
    # Storage
    STORAGE_DIR: Path = Field(
        default_factory=lambda: Path(
            os.getenv("STORAGE_DIR", str(Path(__file__).resolve().parent.parent / "storage" / "uploads"))
        )
    )
    
    # LLM Gateway
    LLM_BASE_URL: str = Field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))
    LLM_API_KEY: str = Field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    LLM_BUDGET_CEILING_USD: float = Field(default_factory=lambda: float(os.getenv("LLM_BUDGET_CEILING_USD", "9.0")))
    
    # Worker lease & queue
    WORKER_LEASE_SECONDS: int = Field(default_factory=lambda: int(os.getenv("WORKER_LEASE_SECONDS", "60")))
    WORKER_POLL_INTERVAL: float = Field(default_factory=lambda: float(os.getenv("WORKER_POLL_INTERVAL", "1.0")))
    DEFAULT_ORG_ID: str = Field(default_factory=lambda: os.getenv("DEFAULT_ORG_ID", "default"))

settings = Settings()
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
