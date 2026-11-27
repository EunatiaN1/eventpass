"""Shared domain status enums matching the PostgreSQL schema."""

from enum import Enum


class TicketStatus(str, Enum):
    ISSUED = "issued"
    LISTED = "listed"
    RESERVED = "reserved"
    SOLD = "sold"
    REFUNDED = "refunded"
    CHECKED_IN = "checked_in"


class ListingStatus(str, Enum):
    ACTIVE = "active"
    RESERVED = "reserved"
    SOLD = "sold"
    CANCELLED = "cancelled"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"


class PaymentProvider(str, Enum):
    PAYFAST = "payfast"
    PAYSTACK = "paystack"
    X402 = "x402"


class ReservationStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
