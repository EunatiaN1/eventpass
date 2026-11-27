"""Pydantic schemas for the x402 agent payment rail."""

from typing import Optional
from pydantic import BaseModel


class X402VerificationResult(BaseModel):
    """Result returned by the x402 facilitator verification helper."""

    is_valid: bool
    payment_reference: str
    buyer_wallet: Optional[str] = None
    reason: Optional[str] = None


class X402SettlementResponse(BaseModel):
    """Response returned when an x402 payment settles and triggers ticket transfer."""

    status: str
    listing_id: str
    ticket_id: str
    payment_reference: str
    network: str
    asset: str
    amount_usdc_micro: int
    buyer_wallet: Optional[str] = None
