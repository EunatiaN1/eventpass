"""Pydantic schemas for gate staff QR validation and single-use check-in."""

from typing import Optional
from pydantic import BaseModel, Field


class CheckInRequest(BaseModel):
    qr_token: str = Field(..., min_length=10)
    event_id: str
    scanner_id: str = Field(default="GateScanner-A1")


class CheckInResponse(BaseModel):
    accepted: bool
    result: str
    reason: str
    ticket_id: Optional[str] = None
    event_id: Optional[str] = None
    owner_wallet: Optional[str] = None
    credential_version: Optional[int] = None
