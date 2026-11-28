"""Fiat payment webhook routes (PayFast and Paystack)."""

import hashlib
import hmac
import json
from typing import Any, Callable, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from supabase import Client

from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.schemas.common import TransactionStatus
from backend.schemas.webhooks import (
    PayFastWebhookPayload,
    PaystackWebhookPayload,
    WebhookResponse,
)
from backend.services.settlement import complete_resale_settlement
from backend.services.solana import finalize_solana_transfer

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _verify_hmac_signature(
    raw_body: bytes,
    signature: Optional[str],
    secret: str,
    digestmod: Callable[[], Any],
) -> bool:
    """Verify an HMAC hex digest signature in constant time."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, digestmod).hexdigest()
    return hmac.compare_digest(expected.lower(), signature.strip().lower())


def _process_webhook_settlement(
    db: Client,
    background_tasks: BackgroundTasks,
    payment_reference: str,
    is_success: bool,
    buyer_wallet_override: Optional[str] = None,
) -> WebhookResponse:
    """Enforce idempotency on payment_reference and settle ticket sale on success."""
    tx_resp = (
        db.table("transactions")
        .select("*")
        .eq("payment_reference", payment_reference)
        .execute()
    )
    if not tx_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction not found for payment_reference={payment_reference}",
        )

    tx = tx_resp.data[0]
    ticket_id: Optional[str] = tx.get("ticket_id")
    buyer_wallet: Optional[str] = buyer_wallet_override or tx.get("buyer_wallet")

    # Idempotency guard: already settled transactions must not re-run settlement
    if tx.get("status") == TransactionStatus.SETTLED.value:
        return WebhookResponse(
            status="already_settled",
            payment_reference=payment_reference,
            ticket_id=ticket_id,
            idempotent=True,
        )

    if not is_success:
        db.table("transactions").update(
            {"status": TransactionStatus.FAILED.value}
        ).eq("payment_reference", payment_reference).execute()
        return WebhookResponse(
            status="failed",
            payment_reference=payment_reference,
            ticket_id=ticket_id,
            idempotent=False,
        )

    if ticket_id:
        complete_resale_settlement(
            db=db,
            payment_reference=payment_reference,
            ticket_id=ticket_id,
            buyer_wallet=buyer_wallet,
            listing_id=tx.get("listing_id"),
            currency=tx.get("currency", "ZAR"),
        )
        background_tasks.add_task(finalize_solana_transfer, ticket_id, buyer_wallet)
    else:
        db.table("transactions").update(
            {"status": TransactionStatus.SETTLED.value}
        ).eq("payment_reference", payment_reference).execute()

    return WebhookResponse(
        status="settled",
        payment_reference=payment_reference,
        ticket_id=ticket_id,
        idempotent=False,
    )


@router.post("/paystack", response_model=WebhookResponse)
async def paystack_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_paystack_signature: Optional[str] = Header(default=None, alias="x-paystack-signature"),
    settings: Settings = Depends(get_settings),
    db: Client = Depends(get_supabase_client),
) -> WebhookResponse:
    """Handle Paystack payment notifications with HMAC-SHA512 verification."""
    raw_body = await request.body()
    if not _verify_hmac_signature(
        raw_body, x_paystack_signature, settings.paystack_secret, hashlib.sha512
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Paystack HMAC signature.",
        )

    try:
        payload_dict = json.loads(raw_body.decode("utf-8"))
        payload = PaystackWebhookPayload.model_validate(payload_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed Paystack webhook payload.",
        ) from exc

    is_success = (
        payload.event == "charge.success" and payload.data.status.lower() == "success"
    )
    return _process_webhook_settlement(
        db=db,
        background_tasks=background_tasks,
        payment_reference=payload.data.reference,
        is_success=is_success,
    )
