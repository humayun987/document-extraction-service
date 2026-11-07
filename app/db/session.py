import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.db.models import Base
from app.utils.logging import logger

connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=15 if "sqlite" not in settings.DATABASE_URL else 5,
    max_overflow=25 if "sqlite" not in settings.DATABASE_URL else 10,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db(retries: int = 5, delay: float = 2.0):
    """
    Initialize database tables with connection retry.
    Never silently falls back to SQLite if PostgreSQL is configured.
    """
    global engine, SessionLocal
    is_sqlite = "sqlite" in settings.DATABASE_URL or os.environ.get("TESTING") == "1"
    
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialized successfully.")
            return
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt}/{retries} failed: {e}")
            if attempt == retries:
                if is_sqlite:
                    logger.error(f"Failed to connect to SQLite: {e}")
                    raise
                else:
                    # In production / Docker Compose, do NOT fall back to local SQLite.
                    # Failing fast ensures healthchecks detect DB issues rather than desyncing containers.
                    raise ConnectionError(
                        f"Failed to connect to configured database at {settings.DATABASE_URL} after {retries} attempts: {e}"
                    )
            time.sleep(delay)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_health() -> bool:
    """Verify database responsiveness for healthchecks."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False
