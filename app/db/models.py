from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True)
    organization_id = Column(String(64), nullable=False, default="default", index=True)
    idempotency_key = Column(String(64), nullable=True, index=True)
    
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    stage = Column(String(32), nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    file_path = Column(String(512), nullable=False)
    file_name = Column(String(256), nullable=False)
    file_type = Column(String(16), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False)
    
    schema_hash = Column(String(64), nullable=False)
    schema_name = Column(String(128), nullable=True)
    schema_data = Column(JSON, nullable=False)
    
    webhook_url = Column(String(512), nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(JSON, nullable=True)
    
    worker_id = Column(String(64), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_org_idempotency"),
        Index("idx_status_lease", "status", "lease_expires_at"),
    )

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "stage": self.stage,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "result": self.result,
            "error": self.error,
        }
