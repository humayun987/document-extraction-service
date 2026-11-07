from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api.routes import router
from app.db.session import init_db
from app.utils.logging import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schema on startup...")
    init_db()
    logger.info("Application startup completed.")
    yield
    logger.info("Application shutting down.")

app = FastAPI(
    title="Document Extraction Service",
    version="1.0.0",
    lifespan=lifespan
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": "HTTP_ERROR", "message": str(exc.detail)}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    msg = "; ".join([f"{'.'.join(str(l) for l in err.get('loc', []))}: {err.get('msg')}" for err in errors])
    return JSONResponse(
        status_code=400,
        content={"code": "VALIDATION_ERROR", "message": msg}
    )

app.include_router(router)

