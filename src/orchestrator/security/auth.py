"""Dashboard & API Authentication and Role-Based Access Control (Point 11.1)."""
from enum import Enum
from typing import Optional
from fastapi import Header, HTTPException, Request
from src.orchestrator.config import settings

class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

def verify_api_token(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None)
) -> UserRole:
    """Verify Bearer token when REQUIRE_AUTH is enabled or when a token is configured."""
    configured_token = settings.api_auth_token
    if not settings.require_auth and not configured_token:
        return UserRole.ADMIN

    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_token:
        token = x_api_token.strip()

    if not token or token != configured_token:
        raise HTTPException(status_code=401, detail="Unauthorized: Valid Bearer token required.")
    return UserRole.ADMIN
