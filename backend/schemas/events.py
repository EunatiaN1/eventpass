"""Pydantic schemas for events and organizer resale controls."""

from typing import Optional
from pydantic import BaseModel, Field


class EventCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=160)
    venue: str = Field(..., min_length=2, max_length=160)
    event_date: str = Field(..., description="ISO-8601 timestamp with timezone offset")
    timezone: str = Field(default="Africa/Johannesburg")
    organizer_wallet: str = Field(..., min_length=4)
    ticket_price_zar: int = Field(..., ge=0)
    resale_enabled: bool = True
    max_resale_price_zar: Optional[int] = Field(default=None, gt=0)
    max_resale_markup_bps: Optional[int] = Field(default=1000, ge=0)
    refund_window_open_at: Optional[str] = None


class EventResaleConfigUpdate(BaseModel):
    resale_enabled: Optional[bool] = None
    max_resale_price_zar: Optional[int] = Field(default=None, gt=0)
    max_resale_markup_bps: Optional[int] = Field(default=None, ge=0)
    resale_cutoff_at: Optional[str] = None


class PrimaryPurchaseRequest(BaseModel):
    buyer_wallet: str = Field(..., min_length=4)
    quantity: int = Field(..., ge=1, le=20)
    tier: str = Field(default="General Admission")
    payment_method: str = Field(default="card")
