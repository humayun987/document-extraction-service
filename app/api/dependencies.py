from fastapi import Header
from app.config import settings

def get_organization_id(x_organization_id: str = Header(default=None)) -> str:
    """Retrieve tenant ID from X-Organization-Id header, defaulting to configured default."""
    if not x_organization_id or not x_organization_id.strip():
        return settings.DEFAULT_ORG_ID
    return x_organization_id.strip()

