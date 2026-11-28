"""Schemas for explicitly simulated checkout confirmations."""

from typing import Literal

from pydantic import BaseModel, Field


class MockSuccessRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1, max_length=80)
    payment_method: Literal["eft", "card", "x402"]


class MockSuccessResponse(BaseModel):
    status: Literal["settled", "already_settled"]
    payment_reference: str
    ticket_id: str
    ticket_ids: list[str]
    payment_method: Literal["eft", "card", "x402"]
    amount_zar: int
    idempotent: bool
    simulation: Literal[True] = True
