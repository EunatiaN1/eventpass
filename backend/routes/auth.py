"""Authentication & rate-limited OTP routes issuing signed HS256 JWTs."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any, Dict
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.auth import AuthenticatedUser, create_access_token, get_current_user
from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.rate_limit import limiter
from backend.services.email import EmailDeliveryError, send_login_code
from backend.schemas.auth import (
    AuthSessionResponse,
    OtpRequest,
    OtpVerifyRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _find_or_create_email_profile(db: Any, email: str) -> Dict[str, Any]:
    """Create a buyer profile once, tolerating two first sign-ins arriving together."""
    existing = db.table("profiles").select("*").eq("email", email).execute()
    if existing.data:
        return existing.data[0]

    user_id = str(uuid.uuid4())
    profile = {
        "id": user_id,
        "wallet_address": f"Email{user_id.replace('-', '')}Devnet",
        "email": email,
        "role": "buyer",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        db.table("profiles").insert(profile).execute()
        return profile
    except Exception:
        # The lower(email) unique index is authoritative if concurrent OTPs race.
        existing = db.table("profiles").select("*").eq("email", email).execute()
        if existing.data:
            return existing.data[0]
        raise


@router.post("/otp")
@limiter.limit("5/minute")
async def request_otp(
    request: Request,
    payload: OtpRequest,
    db: Any = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Generate a 6-digit email OTP (strictly rate-limited to 5 requests/minute)."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    email = str(payload.email).strip().lower()
    code_hash = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        f"{email}:{code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    db.table("otp_challenges").insert(
        {
            "id": str(uuid.uuid4()),
            "email": email,
            "code_hash": code_hash,
            "expires_at": expires_at,
            "consumed": False,
            "attempts": 0,
        }
    ).execute()

    response: Dict[str, Any] = {
        "status": "otp_sent",
        "email": email,
        "expires_at": expires_at,
    }
    if settings.resend_api_key:
        try:
            await send_login_code(
                email=email,
                code=code,
                api_key=settings.resend_api_key,
                from_email=settings.auth_from_email,
            )
        except EmailDeliveryError as exc:
            db.table("otp_challenges").update({"consumed": True}).eq(
                "code_hash", code_hash
            ).execute()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
    else:
        db.table("otp_challenges").update({"consumed": True}).eq(
            "code_hash", code_hash
        ).execute()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Passwordless email sign-in is not configured.",
        )
    return response


@router.post("/verify-otp", response_model=AuthSessionResponse, response_model_exclude_none=True)
@limiter.limit("10/minute")
async def verify_otp(
    request: Request,
    payload: OtpVerifyRequest,
    response: Response,
    db: Any = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> AuthSessionResponse:
    """Verify email OTP and issue a signed JWT session token."""
    email = str(payload.email).lower()
    challenges = db.table("otp_challenges").select("*").eq("email", email).execute().data or []
    active = [c for c in challenges if not c.get("consumed")]
    if not active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active OTP challenge found for this email.",
        )

    latest = max(active, key=lambda challenge: challenge.get("created_at", ""))
    exp = datetime.fromisoformat(latest["expires_at"].replace("Z", "+00:00"))
    if exp <= datetime.now(timezone.utc):
        db.table("otp_challenges").update({"consumed": True}).eq("id", latest["id"]).execute()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Code expired. Request a new code.",
        )

    if int(latest.get("attempts", 0)) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect codes. Request a new code.",
        )

    candidate_hash = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        f"{email}:{payload.otp_code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(candidate_hash, latest["code_hash"]):
        attempts = int(latest.get("attempts", 0)) + 1
        db.table("otp_challenges").update(
            {"attempts": attempts, "consumed": attempts >= 5}
        ).eq("id", latest["id"]).execute()
        if attempts >= 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many incorrect codes. Request a new code.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid code. Check the 6 digits and try again.",
        )

    db.table("otp_challenges").update({"consumed": True}).eq("id", latest["id"]).execute()

    profile = _find_or_create_email_profile(db, email)

    token = create_access_token(
        user_id=profile["id"],
        wallet=profile["wallet_address"],
        role=profile["role"],
        email=email,
        settings=settings,
    )
    response.set_cookie(
        key="eventpass_session",
        value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.environment == "production",
        samesite="none" if settings.environment == "production" else "lax",
        path="/",
    )
    return AuthSessionResponse(
        access_token=token if request.headers.get("x-auth-client") == "native" else None,
        user_id=profile["id"],
        wallet=profile["wallet_address"],
        role=profile["role"],
        email=email,
    )


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> Response:
    """Clear the HttpOnly browser session cookie."""
    response.delete_cookie(
        key="eventpass_session",
        httponly=True,
        secure=settings.environment == "production",
        samesite="none" if settings.environment == "production" else "lax",
        path="/",
    )
    return response


@router.get("/me", response_model=AuthenticatedUser)
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Return the currently authenticated user profile."""
    return current_user
