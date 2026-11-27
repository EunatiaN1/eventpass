"""Pydantic schemas for fiat payment webhooks (PayFast & Paystack)."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PayFastWebhookPayload(BaseModel):
    """Inbound PayFast ITN / webhook payload."""

    model_config = ConfigDict(extra="allow")

    m_payment_id: str = Field(..., description="Unique EventPass payment reference")
    pf_payment_id: Optional[str] = Field(None, description="PayFast transaction ID")
    payment_status: str = Field(..., description="PayFast status e.g. COMPLETE, FAILED")
    amount_gross: Optional[str] = None
    custom_str1: Optional[str] = Field(None, description="Optional buyer wallet address")


class PaystackWebhookData(BaseModel):
    """Nested data object in a Paystack webhook event."""

    model_config = ConfigDict(extra="allow")

    reference: str = Field(..., description="Unique EventPass payment reference")
    status: str = Field(..., description="Paystack transaction status e.g. success")
    amount: Optional[int] = Field(None, description="Amount in minor units (kobo/cents)")


class PaystackWebhookPayload(BaseModel):
    """Inbound Paystack webhook event."""

    model_config = ConfigDict(extra="allow")

    event: str = Field(..., description="Webhook event type e.g. charge.success")
    data: PaystackWebhookData


class WebhookResponse(BaseModel):
    """Standardized webhook acknowledgement response."""

    status: str
    payment_reference: str
    ticket_id: Optional[str] = None
    idempotent: bool = False
