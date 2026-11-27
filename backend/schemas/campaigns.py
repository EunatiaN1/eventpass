"""Strict Pydantic schemas for social resale campaigns, listings, reservations, and checkout."""

from typing import List
from pydantic import BaseModel, Field, conint, constr


class CampaignListingItemInput(BaseModel):
    ticket_id: constr(min_length=2, max_length=64, strip_whitespace=True)
    asking_price_zar: conint(gt=0)


class CampaignCreateRequest(BaseModel):
    seller_wallet: constr(min_length=4, max_length=64, strip_whitespace=True)
    title: constr(min_length=3, max_length=160, strip_whitespace=True)
    items: List[CampaignListingItemInput] = Field(..., min_length=1, max_length=20)


class ListingCancelRequest(BaseModel):
    seller_wallet: constr(min_length=4, max_length=64, strip_whitespace=True)


class ListingReserveRequest(BaseModel):
    buyer_wallet: constr(min_length=4, max_length=64, strip_whitespace=True)
    ttl_seconds: conint(ge=60, le=3600) = 600


class CheckoutInitiateRequest(BaseModel):
    listing_id: constr(min_length=2, max_length=64, strip_whitespace=True)
    buyer_wallet: constr(min_length=4, max_length=64, strip_whitespace=True)
    payment_method: constr(
        pattern="^(eventpass_wallet|card|eft|payfast|payflex|x402)$"
    )


class CheckoutConfirmDemoRequest(BaseModel):
    payment_reference: constr(min_length=4, max_length=128, strip_whitespace=True)
    simulate_outcome: constr(pattern="^(success|failed)$") = "success"
