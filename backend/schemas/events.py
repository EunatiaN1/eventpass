"""Strict Pydantic schemas for events and organizer resale controls."""

from typing import Optional
from pydantic import BaseModel, Field, conint, constr


class EventCreateRequest(BaseModel):
    title: constr(min_length=2, max_length=160, strip_whitespace=True)
    venue: constr(min_length=2, max_length=160, strip_whitespace=True)
    event_date: constr(min_length=10, max_length=64, strip_whitespace=True) = Field(
        ..., description="ISO-8601 timestamp with timezone offset"
    )
    timezone: constr(min_length=3, max_length=64, strip_whitespace=True) = "Africa/Johannesburg"
    organizer_wallet: constr(min_length=4, max_length=64, strip_whitespace=True)
    ticket_price_zar: conint(ge=0)
    resale_enabled: bool = True
    max_resale_price_zar: Optional[conint(gt=0)] = None
    max_resale_markup_bps: Optional[conint(ge=0)] = 1000
    refund_window_open_at: Optional[str] = None


class EventResaleConfigUpdate(BaseModel):
    resale_enabled: Optional[bool] = None
    max_resale_price_zar: Optional[conint(gt=0)] = None
    max_resale_markup_bps: Optional[conint(ge=0)] = None
    resale_cutoff_at: Optional[str] = None


class PrimaryPurchaseRequest(BaseModel):
    buyer_wallet: constr(min_length=4, max_length=64, strip_whitespace=True)
    quantity: conint(ge=1, le=20)
    tier: constr(min_length=2, max_length=64, strip_whitespace=True) = "General Admission"
    payment_method: constr(pattern="^(card|eft|x402)$") = "card"
