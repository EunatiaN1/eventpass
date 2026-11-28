"""Strict Pydantic schemas for authentication and OTP flows."""

from typing import Optional
from pydantic import BaseModel, EmailStr, constr


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: constr(min_length=6, max_length=6, pattern="^[0-9]{6}$")


class AuthSessionResponse(BaseModel):
    access_token: Optional[str] = None
    user_id: str
    wallet: str
    role: str
    email: Optional[str] = None
