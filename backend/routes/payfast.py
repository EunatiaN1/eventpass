"""PayFast Sandbox/Production checkout and ITN routes.

ITNs are accepted only after signature verification and PayFast's server-side
validation endpoint returns VALID. Verified primary ticket payments mint Core assets through the EventPass Anchor
program before the transaction is marked settled.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from supabase import Client

from backend.auth import AuthenticatedUser, get_current_user
from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.schemas.common import TransactionStatus
from backend.schemas.webhooks import WebhookResponse
from backend.services.payfast import payfast_signature, verify_payfast_signature
from backend.services.solana import mint_ticket
from backend.services.ledger import append_ownership_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments/payfast", tags=["PayFast"])


def _configured(settings: Settings) -> None:
    if not all((settings.payfast_merchant_id, settings.payfast_merchant_key, settings.payfast_passphrase)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PayFast merchant ID, merchant key, and passphrase are required.",
        )


def _base_fields(settings: Settings, payment_reference: str, amount: int, item_name: str) -> list[tuple[str, str]]:
    fields = [
        ("merchant_id", settings.payfast_merchant_id),
        ("merchant_key", settings.payfast_merchant_key),
        ("return_url", f"{settings.app_public_url.rstrip('/')}/?payment=return"),
        ("cancel_url", f"{settings.app_public_url.rstrip('/')}/?payment=cancel"),
        ("notify_url", f"{settings.app_public_url.rstrip('/')}/api/payments/payfast/itn"),
        ("m_payment_id", payment_reference),
        ("amount", f"{Decimal(amount):.2f}"),
        ("item_name", item_name[:100]),
    ]
    fields.append(("signature", payfast_signature(fields, settings.payfast_passphrase)))
    return fields


@router.post("/{payment_reference}/checkout")
async def create_checkout(
    payment_reference: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Client = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Create signed PayFast hosted-checkout fields for an owned pending resale."""
    _configured(settings)
    response = (
        db.table("transactions")
        .select("*")
        .eq("payment_reference", payment_reference)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Payment reference not found.")
    tx = response.data[0]
    if tx.get("buyer_wallet") != current_user.wallet:
        raise HTTPException(status_code=403, detail="Payment does not belong to this account.")
    if tx.get("provider") != "payfast" or tx.get("status") != TransactionStatus.PENDING.value:
        raise HTTPException(status_code=409, detail="Payment is not a pending PayFast checkout.")
    if tx.get("listing_id"):
        raise HTTPException(
            status_code=409,
            detail="PayFast resale checkout is disabled until the deployed program supports transfer delegation.",
        )
    fields = _base_fields(
        settings, payment_reference, int(tx["amount"]), f"EventPass purchase {payment_reference}"
    )
    action = (
        "https://sandbox.payfast.co.za/eng/process"
        if settings.payfast_sandbox
        else "https://www.payfast.co.za/eng/process"
    )
    return {"action": action, "method": "POST", "fields": dict(fields)}


async def _payfast_validate_notification(raw_body: bytes, settings: Settings) -> bool:
    endpoint = (
        "https://sandbox.payfast.co.za/eng/query/validate"
        if settings.payfast_sandbox
        else "https://www.payfast.co.za/eng/query/validate"
    )
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=False) as client:
        response = await client.post(
            endpoint,
            content=raw_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    response.raise_for_status()
    return response.text.strip() == "VALID"


@router.post("/itn", response_model=WebhookResponse)
async def receive_itn(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Client = Depends(get_supabase_client),
) -> WebhookResponse:
    """Verify a PayFast ITN signature, source validation, merchant, reference and amount."""
    _configured(settings)
    raw_body = await request.body()
    try:
        fields = parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True, strict_parsing=True)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Malformed PayFast ITN form.") from exc

    names = [name.lower() for name, _ in fields]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=400, detail="Duplicate PayFast ITN fields are not allowed.")
    values = dict(fields)
    if not verify_payfast_signature(fields, settings.payfast_passphrase):
        raise HTTPException(status_code=401, detail="Invalid PayFast ITN signature.")
    try:
        if not await _payfast_validate_notification(raw_body, settings):
            raise HTTPException(status_code=401, detail="PayFast ITN validation was rejected.")
    except httpx.HTTPError as exc:
        logger.exception("PayFast ITN validation request failed")
        raise HTTPException(status_code=503, detail="Could not validate notification with PayFast.") from exc

    if values.get("merchant_id") != settings.payfast_merchant_id:
        raise HTTPException(status_code=401, detail="PayFast merchant ID does not match.")
    payment_reference = values.get("m_payment_id", "")
    if not payment_reference:
        raise HTTPException(status_code=400, detail="PayFast ITN has no payment reference.")

    response = (
        db.table("transactions")
        .select("*")
        .eq("payment_reference", payment_reference)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Payment reference not found.")
    tx = response.data[0]
    if tx.get("provider") != "payfast":
        raise HTTPException(status_code=409, detail="Payment reference is not a PayFast transaction.")
    try:
        received = Decimal(values.get("amount_gross", "")).quantize(Decimal("0.01"))
        expected = Decimal(int(tx["amount"])).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail="PayFast ITN amount is invalid.") from exc
    if received != expected:
        raise HTTPException(status_code=409, detail="PayFast amount does not match the order.")

    if tx.get("status") == TransactionStatus.SETTLED.value:
        return WebhookResponse(
            status="already_settled",
            payment_reference=payment_reference,
            ticket_id=tx.get("ticket_id"),
            idempotent=True,
        )

    payment_status = values.get("payment_status", "").upper()
    if payment_status == "FAILED":
        db.table("transactions").update({"status": TransactionStatus.FAILED.value}).eq(
            "payment_reference", payment_reference
        ).execute()
        return WebhookResponse(status="failed", payment_reference=payment_reference)
    if payment_status != "COMPLETE":
        raise HTTPException(status_code=409, detail="PayFast payment is not complete.")
    if not tx.get("listing_id"):
        raise HTTPException(
            status_code=409,
            detail="Primary ticket minting is not enabled until the EventPass program is deployed.",
        )

    if tx.get("listing_id"):
        raise HTTPException(
            status_code=409,
            detail="PayFast resale transfer delegation is not configured.",
        )

    tickets = (
        db.table("tickets")
        .select("*")
        .eq("order_reference", payment_reference)
        .execute()
        .data or []
    )
    if not tickets:
        raise HTTPException(status_code=404, detail="No tickets are attached to this payment.")
    event_response = db.table("events").select("*").eq("id", tickets[0]["event_id"]).execute()
    if not event_response.data:
        raise HTTPException(status_code=404, detail="Ticket event was not found.")
    event = event_response.data[0]
    metadata_base = f"{settings.app_public_url.rstrip('/')}/api/tickets"
    for ticket in tickets:
        if ticket.get("asset_address"):
            continue
        try:
            asset_address, signature = await mint_ticket(
                event_id=str(event["id"]),
                ticket_id=str(ticket["id"]),
                name=f"{event['title']} Ticket",
                uri=f"{metadata_base}/{ticket['id']}/metadata.json",
                owner_wallet=ticket["owner_wallet"],
                settings=settings,
            )
            db.table("tickets").update({
                "asset_address": asset_address,
                "status": "issued",
            }).eq("id", ticket["id"]).execute()
            append_ownership_history(
                db=db,
                ticket_id=ticket["id"],
                action="issued",
                from_wallet=event.get("organizer_wallet"),
                to_wallet=ticket["owner_wallet"],
                reference=payment_reference,
            )
            logger.info(
                "PayFast ticket minted ticket_id=%s asset=%s signature=%s",
                ticket["id"], asset_address, signature,
            )
        except Exception as exc:
            logger.exception("PayFast ticket mint failed ticket_id=%s", ticket["id"])
            raise HTTPException(
                status_code=503,
                detail=f"Payment was verified, but ticket minting is pending reconciliation for {ticket['id']}.",
            ) from exc

    db.table("transactions").update({"status": TransactionStatus.SETTLED.value}).eq(
        "payment_reference", payment_reference
    ).execute()
    return WebhookResponse(
        status="settled",
        payment_reference=payment_reference,
        ticket_id=tickets[0]["id"],
        idempotent=False,
    )
