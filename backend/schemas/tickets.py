"""Pydantic schemas for individual tickets, QR credentials, and 75% refunds."""

from typing import Optional
from pydantic import BaseModel, Field


class RefundRequestCreate(BaseModel):
    requester_wallet: str = Field(..., min_length=4)


class RefundResponse(BaseModel):
    refund_id: str
    ticket_id: str
    original_price_zar: int
    refund_amount_zar: int
    retained_amount_zar: int
    status: str
    payout_due_at: str
    credential_version: int
    message: str


class TicketCredentialResponse(BaseModel):
    ticket_id: str
    event_id: str
    credential_version: int
    status: str
    qr_token: str
    owner_wallet: str
    asset_address: str
