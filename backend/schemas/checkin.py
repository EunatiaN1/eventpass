"""Strict Pydantic schemas for gate staff QR validation and single-use check-in."""

from typing import Optional
from pydantic import BaseModel, constr


class CheckInRequest(BaseModel):
    qr_token: constr(min_length=10, max_length=1024, strip_whitespace=True)
    event_id: constr(min_length=2, max_length=64, strip_whitespace=True)
    scanner_id: constr(min_length=2, max_length=64, strip_whitespace=True) = "GateScanner-A1"


class CheckInResponse(BaseModel):
    accepted: bool
    result: str
    reason: str
    ticket_id: Optional[str] = None
    event_id: Optional[str] = None
    owner_wallet: Optional[str] = None
    credential_version: Optional[int] = None
