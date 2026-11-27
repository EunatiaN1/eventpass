"""Pydantic schemas for social resale campaigns, listings, reservations, and checkout."""

from typing import List, Optional
from pydantic import BaseModel, Field


class CampaignListingItemInput(BaseModel):
    ticket_id: str
    asking_price_zar: int = Field(..., gt=0)


class CampaignCreateRequest(BaseModel):
    seller_wallet: str = Field(..., min_length=4)
    title: str = Field(..., min_length=3, max_length=160)
    items: List[CampaignListingItemInput] = Field(..., min_length=1)


class ListingCancelRequest(BaseModel):
    seller_wallet: str = Field(..., min_length=4)


class ListingReserveRequest(BaseModel):
    buyer_wallet: str = Field(..., min_length=4)
    ttl_seconds: int = Field(default=600, ge=60, le=3600)


class CheckoutInitiateRequest(BaseModel):
    listing_id: str
    buyer_wallet: str = Field(..., min_length=4)
    payment_method: str = Field(
        ...,
        pattern="^(eventpass_wallet|card|eft|payfast|payflex|x402)$",
    )


class CheckoutConfirmDemoRequest(BaseModel):
    payment_reference: str
    simulate_outcome: str = Field(default="success", pattern="^(success|failed)$")
