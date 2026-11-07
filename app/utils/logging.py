import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict

class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects with ISO 8601 timestamps."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add custom structured attributes if passed via extra
        for key, val in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
                "created", "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process"
            }:
                # Sanitize to never leak secrets
                if "key" in key.lower() or "secret" in key.lower() or "token" in key.lower() and "count" not in key.lower():
                    log_obj[key] = "***REDACTED***"
                else:
                    log_obj[key] = val
                    
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj, default=str)

def get_logger(name: str = "outcome-extraction") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger

logger = get_logger()

