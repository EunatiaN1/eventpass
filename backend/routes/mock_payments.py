"""Backend-only controls and idempotent test payment completion."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth import AuthenticatedUser, get_current_user
from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.schemas.mock_payments import MockSuccessRequest, MockSuccessResponse

router = APIRouter(tags=["simulated checkout"])


@router.get("/api/checkout/config")
async def checkout_config(
    amount_zar: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Expose only the public Solana Devnet payment destination needed by checkout."""
    from decimal import Decimal, ROUND_HALF_UP

    amount_usdc = (Decimal(amount_zar) * Decimal(settings.zar_to_usdc_rate)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return {
        "x402_pay_to_address": settings.x402_pay_to_address,
        "network": "solana-devnet",
        "usdc_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "amount_usdc": str(amount_usdc),
    }


@router.patch("/api/checkout/{payment_reference}/method")
async def update_simulated_checkout_method(
    payment_reference: str,
    payment_method: str = Query(pattern="^(eft|card|x402)$"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Any = Depends(get_supabase_client),
) -> dict[str, str]:
    """Select the simulated method before confirmation, while the order is pending."""
    tx_resp = (
        db.table("transactions")
        .select("*")
        .eq("payment_reference", payment_reference)
        .execute()
    )
    if not tx_resp.data:
        raise HTTPException(status_code=404, detail="Checkout transaction not found.")
    transaction = tx_resp.data[0]
    if transaction.get("buyer_wallet") != current_user.wallet:
        raise HTTPException(status_code=403, detail="Checkout does not belong to this account.")
    if transaction.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Checkout is no longer pending.")
    db.table("transactions").update({"payment_method": payment_method}).eq(
        "payment_reference", payment_reference
    ).execute()
    return {"payment_reference": payment_reference, "payment_method": payment_method}


@router.post(
    "/api/webhooks/mock-success",
    response_model=MockSuccessResponse,
    status_code=status.HTTP_200_OK,
)
async def mock_success(
    payload: MockSuccessRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Any = Depends(get_supabase_client),
) -> MockSuccessResponse:
    """Settle a test order atomically; this endpoint never verifies or moves funds."""
    ticket_resp = db.table("tickets").select("*").eq("id", payload.ticket_id).execute()
    if not ticket_resp.data:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    ticket = ticket_resp.data[0]

    if ticket.get("owner_wallet") != current_user.wallet:
        raise HTTPException(status_code=403, detail="Ticket does not belong to this account.")

    order_reference = ticket.get("order_reference")
    if not order_reference:
        raise HTTPException(status_code=409, detail="Ticket is not part of a simulated checkout.")

    transaction_resp = (
        db.table("transactions")
        .select("*")
        .eq("payment_reference", order_reference)
        .execute()
    )
    if not transaction_resp.data:
        raise HTTPException(status_code=404, detail="Checkout transaction not found.")
    transaction = transaction_resp.data[0]

    if transaction.get("buyer_wallet") != current_user.wallet:
        raise HTTPException(status_code=403, detail="Checkout does not belong to this account.")
    if transaction.get("payment_method") != payload.payment_method:
        raise HTTPException(status_code=409, detail="Payment method does not match this checkout.")

    try:
        rpc_result = db.rpc(
            "settle_mock_payment",
            {"p_ticket_id": payload.ticket_id, "p_payment_method": payload.payment_method},
        ).execute()
        result = rpc_result.data
        if isinstance(result, list):
            result = result[0] if result else None
        if not isinstance(result, dict):
            raise ValueError("Settlement returned no result.")
    except AttributeError as exc:
        # Lightweight in-memory stores use the same all-or-nothing operation locally.
        lock = getattr(db, "lock", None)
        if lock is None:
            raise HTTPException(status_code=503, detail="Atomic settlement is unavailable.") from exc
        with lock:
            try:
                result = db.settle_mock_payment(payload.ticket_id, payload.payment_method)
            except ValueError as settlement_error:
                raise HTTPException(status_code=409, detail=str(settlement_error)) from settlement_error
    except Exception as exc:
        detail = str(exc)
        if "already settled" in detail.lower() or "payment method" in detail.lower():
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=409, detail="Checkout could not be settled.") from exc

    return MockSuccessResponse(
        status=result["status"],
        payment_reference=result["payment_reference"],
        ticket_id=payload.ticket_id,
        ticket_ids=result["ticket_ids"],
        payment_method=payload.payment_method,
        amount_zar=int(result["amount_zar"]),
        idempotent=bool(result["idempotent"]),
    )
