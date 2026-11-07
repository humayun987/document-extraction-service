import hashlib
import json
from typing import Any, Dict

def hash_bytes(data: bytes) -> str:
    """Calculate SHA-256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()

def canonicalize_schema_json(schema_obj: Dict[str, Any]) -> str:
    """Serialize schema deterministically with sorted keys and compact separators."""
    return json.dumps(schema_obj, sort_keys=True, separators=(",", ":"))

def hash_schema(schema_obj: Dict[str, Any]) -> str:
    """Calculate SHA-256 of canonicalized schema JSON."""
    canonical = canonicalize_schema_json(schema_obj)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def generate_idempotency_key(org_id: str, file_hash: str, schema_hash: str) -> str:
    """Generate scoped idempotency key across tenant, document, and schema."""
    token = f"{org_id}:{file_hash}:{schema_hash}"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

