"""Integer-safe pricing, fee, price-cap, and timezone-aware refund window helpers."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

MARKETPLACE_FEE_BPS = 500  # 5.00%
REFUND_RATE_BPS = 7500     # 75.00%
BPS_DENOMINATOR = 10_000


@dataclass(frozen=True)
class ResaleBreakdown:
    asking_price_zar: int
    marketplace_fee_zar: int
    seller_proceeds_zar: int


@dataclass(frozen=True)
class RefundBreakdown:
    original_price_zar: int
    refund_amount_zar: int
    retained_amount_zar: int


@dataclass(frozen=True)
class RefundWindowStatus:
    eligible: bool
    reason: Optional[str]
    cutoff_at_local: str
    event_timezone: str


def calculate_resale_breakdown_zar(
    asking_price_zar: int, fee_bps: int = MARKETPLACE_FEE_BPS
) -> ResaleBreakdown:
    """Compute 5% marketplace fee and 95% seller proceeds using integer arithmetic."""
    if asking_price_zar <= 0:
        raise ValueError("Asking price must be positive.")
    fee = (asking_price_zar * fee_bps) // BPS_DENOMINATOR
    proceeds = asking_price_zar - fee
    return ResaleBreakdown(
        asking_price_zar=asking_price_zar,
        marketplace_fee_zar=fee,
        seller_proceeds_zar=proceeds,
    )


def calculate_unsold_refund_zar(original_price_zar: int) -> RefundBreakdown:
    """Compute 75% unsold-ticket refund and 25% retained amount using integer arithmetic."""
    if original_price_zar < 0:
        raise ValueError("Original price cannot be negative.")
    refund_amount = (original_price_zar * REFUND_RATE_BPS) // BPS_DENOMINATOR
    retained = original_price_zar - refund_amount
    return RefundBreakdown(
        original_price_zar=original_price_zar,
        refund_amount_zar=refund_amount,
        retained_amount_zar=retained,
    )


def validate_resale_price_cap(
    asking_price_zar: int, original_price_zar: int, event: Dict[str, Any]
) -> Optional[str]:
    """Return an error message if asking_price_zar exceeds the organizer's cap, else None."""
    if asking_price_zar <= 0:
        return "Asking price must be greater than zero."

    max_fixed = event.get("max_resale_price_zar")
    if max_fixed is not None and asking_price_zar > int(max_fixed):
        return f"Asking price R{asking_price_zar} exceeds organizer cap of R{max_fixed}."

    max_markup_bps = event.get("max_resale_markup_bps")
    if max_markup_bps is not None:
        max_by_markup = original_price_zar + (
            (original_price_zar * int(max_markup_bps)) // BPS_DENOMINATOR
        )
        if asking_price_zar > max_by_markup:
            return (
                f"Asking price R{asking_price_zar} exceeds maximum markup cap of R{max_by_markup}."
            )
    return None


def _parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def evaluate_refund_window(
    event: Dict[str, Any], now_utc: Optional[datetime] = None
) -> RefundWindowStatus:
    """Enforce refund window opening and 15-calendar-day cutoff in the event's IANA timezone.

    Cutoff closes at the start of the calendar day 14 days before the event
    (i.e. requests are permitted up to 15 calendar days before the event date in local time;
    from 14 days before the event onward, requests are rejected).
    """
    tz_name = event.get("timezone") or "Africa/Johannesburg"
    tz = ZoneInfo(tz_name)
    now_local = (now_utc or datetime.now(timezone.utc)).astimezone(tz)

    event_dt_local = _parse_iso(event["event_date"]).astimezone(tz)
    cutoff_days = max(int(event.get("refund_cutoff_days", 15)), 15)
    # 15 calendar days before event: inclusive through the end of (event_date - 15 days),
    # so cutoff begins at 00:00:00 of (event_date - 14 days) in event's local timezone.
    cutoff_date = event_dt_local.date() - timedelta(days=cutoff_days - 1)
    cutoff_local = datetime(
        cutoff_date.year, cutoff_date.month, cutoff_date.day, 0, 0, 0, tzinfo=tz
    )

    open_at_raw = event.get("refund_window_open_at")
    if open_at_raw:
        open_local = _parse_iso(open_at_raw).astimezone(tz)
        if now_local < open_local:
            return RefundWindowStatus(
                eligible=False,
                reason=f"Refund window has not opened yet (opens {open_local.isoformat()}).",
                cutoff_at_local=cutoff_local.isoformat(),
                event_timezone=tz_name,
            )

    if now_local >= cutoff_local:
        return RefundWindowStatus(
            eligible=False,
            reason=(
                f"Refund window closed at {cutoff_local.isoformat()} "
                f"(15-calendar-day cutoff before event)."
            ),
            cutoff_at_local=cutoff_local.isoformat(),
            event_timezone=tz_name,
        )

    return RefundWindowStatus(
        eligible=True,
        reason=None,
        cutoff_at_local=cutoff_local.isoformat(),
        event_timezone=tz_name,
    )
