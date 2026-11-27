"""Authentication & rate-limited OTP routes issuing signed HS256 JWTs."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any, Dict
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.auth import AuthenticatedUser, create_access_token, get_current_user
from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.rate_limit import limiter
from backend.schemas.auth import (
    AuthTokenResponse,
    OtpRequest,
    OtpVerifyRequest,
    WalletAuthRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _ensure_profile(
    db: Any,
    wallet: str,
    email: str | None = None,
) -> Dict[str, Any]:
    """Find or create a user profile record (default role='buyer')."""
    if email:
        by_email = db.table("profiles").select("*").eq("email", email).execute()
        if by_email.data:
            return by_email.data[0]
    by_wallet = db.table("profiles").select("*").eq("wallet_address", wallet).execute()
    if by_wallet.data:
        return by_wallet.data[0]

    profile = {
        "id": str(uuid.uuid4()),
        "wallet_address": wallet,
        "email": email,
        "role": "buyer",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.table("profiles").insert(profile).execute()
    return profile


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
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    db.table("otp_challenges").insert(
        {
            "id": str(uuid.uuid4()),
            "email": str(payload.email).lower(),
            "code_hash": code_hash,
            "expires_at": expires_at,
            "consumed": False,
        }
    ).execute()

    response: Dict[str, Any] = {
        "status": "otp_sent",
        "email": str(payload.email).lower(),
        "expires_at": expires_at,
    }
    # Only surface sandbox OTP hint in local non-production dev store mode
    if settings.use_dev_store and settings.environment != "production":
        response["dev_sandbox_otp"] = code
    return response


@router.post("/verify-otp", response_model=AuthTokenResponse)
@limiter.limit("10/minute")
async def verify_otp(
    request: Request,
    payload: OtpVerifyRequest,
    db: Any = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> AuthTokenResponse:
    """Verify email OTP and issue a signed JWT session token."""
    email = str(payload.email).lower()
    challenges = db.table("otp_challenges").select("*").eq("email", email).execute().data or []
    active = [c for c in challenges if not c.get("consumed")]
    if not active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active OTP challenge found for this email.",
        )

    latest = active[-1]
    exp = datetime.fromisoformat(latest["expires_at"].replace("Z", "+00:00"))
    if exp <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP code has expired.",
        )

    candidate_hash = hashlib.sha256(payload.otp_code.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(candidate_hash, latest["code_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP code.",
        )

    db.table("otp_challenges").update({"consumed": True}).eq("id", latest["id"]).execute()

    clean = email.split("@")[0].replace(".", "")
    derived_wallet = f"Email{clean[:12].ljust(12, '0')}DevnetPass1111111111"
    profile = _ensure_profile(db, wallet=derived_wallet, email=email)

    token = create_access_token(
        user_id=profile["id"],
        wallet=profile["wallet_address"],
        role=profile["role"],
        email=email,
        settings=settings,
    )
    return AuthTokenResponse(
        access_token=token,
        user_id=profile["id"],
        wallet=profile["wallet_address"],
        role=profile["role"],
        email=email,
    )


@router.post("/wallet", response_model=AuthTokenResponse)
@limiter.limit("20/minute")
async def authenticate_wallet(
    request: Request,
    payload: WalletAuthRequest,
    db: Any = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> AuthTokenResponse:
    """Authenticate a Solana Devnet wallet session and issue a signed JWT."""
    profile = _ensure_profile(db, wallet=payload.wallet)
    token = create_access_token(
        user_id=profile["id"],
        wallet=profile["wallet_address"],
        role=profile["role"],
        email=profile.get("email"),
        settings=settings,
    )
    return AuthTokenResponse(
        access_token=token,
        user_id=profile["id"],
        wallet=profile["wallet_address"],
        role=profile["role"],
        email=profile.get("email"),
    )


@router.get("/me", response_model=AuthenticatedUser)
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Return the currently authenticated user profile."""
    return current_user
