"""Strict Pydantic schemas for authentication and OTP flows."""

from typing import Optional
from pydantic import BaseModel, EmailStr, constr


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: constr(min_length=6, max_length=6, pattern="^[0-9]{6}$")


class WalletAuthRequest(BaseModel):
    wallet: constr(min_length=16, max_length=64, strip_whitespace=True)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    wallet: str
    role: str
    email: Optional[str] = None
