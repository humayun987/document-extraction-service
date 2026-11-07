import time
from sqlalchemy import create_engine
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
    """Initialize database tables with connection retry."""
    global engine, SessionLocal
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialized successfully.")
            return
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt}/{retries} failed: {e}")
            if attempt == retries:
                # If Postgres is not up, fallback gracefully to SQLite for local development/testing
                logger.error("Could not connect to configured DATABASE_URL. Falling back to local SQLite.")
                fallback_url = "sqlite:///./extraction.db"
                engine = create_engine(fallback_url, connect_args={"check_same_thread": False})
                SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                Base.metadata.create_all(bind=engine)
                return
            time.sleep(delay)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

