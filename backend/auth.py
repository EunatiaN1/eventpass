"""JWT authentication and DB-backed RBAC dependencies for FastAPI."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from pydantic import BaseModel

from backend.config import Settings, get_settings
from backend.database import get_supabase_client

bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """Verified user identity extracted from the bearer JWT and database profile."""

    id: str
    wallet: str
    email: Optional[str] = None
    role: str = "buyer"


def create_access_token(
    user_id: str,
    wallet: str,
    role: str,
    settings: Settings,
    email: Optional[str] = None,
) -> str:
    """Create a signed HS256 JWT session token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "wallet": wallet,
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
    db: Any = Depends(get_supabase_client),
) -> AuthenticatedUser:
    """Validate Bearer JWT and resolve authoritative user role from the database."""
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = claims.get("sub")
    wallet = claims.get("wallet")
    if not user_id or not wallet:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims.",
        )

    # Check authoritative role in profiles table
    role = claims.get("role", "buyer")
    profile_resp = db.table("profiles").select("*").eq("id", user_id).execute()
    if profile_resp.data:
        role = profile_resp.data[0].get("role", role)

    return AuthenticatedUser(
        id=user_id,
        wallet=wallet,
        email=claims.get("email"),
        role=role,
    )


def require_organizer_or_admin(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Any = Depends(get_supabase_client),
) -> AuthenticatedUser:
    """Restrict route access to users with 'organizer' or 'admin' role in the database."""
    profile_resp = db.table("profiles").select("role").eq("id", current_user.id).execute()
    db_role = (
        profile_resp.data[0].get("role") if profile_resp.data else current_user.role
    )
    if db_role not in ("organizer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organizer or admin role required for this action.",
        )
    return current_user
