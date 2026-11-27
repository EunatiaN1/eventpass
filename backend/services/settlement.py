"""Unified resale settlement, credential rotation, and campaign synchronization."""

from typing import Any, Optional

from backend.schemas.common import (
    ListingStatus,
    ReservationStatus,
    TicketStatus,
    TransactionStatus,
)
from backend.services.ledger import (
    append_audit_log,
    append_ownership_history,
    record_resale_ledger,
)
from backend.services.pricing import calculate_resale_breakdown_zar


def sync_campaign_status(db: Any, campaign_id: Optional[str]) -> None:
    """Mark a campaign 'sold_out' only when all its listings are sold; keep 'active' otherwise."""
    if not campaign_id:
        return
    listings_resp = (
        db.table("resale_listings")
        .select("id, status")
        .eq("campaign_id", campaign_id)
        .execute()
    )
    listings = listings_resp.data or []
    if not listings:
        return

    statuses = {row.get("status") for row in listings}
    if statuses == {ListingStatus.SOLD.value}:
        new_status = "sold_out"
    elif ListingStatus.ACTIVE.value in statuses or ListingStatus.RESERVED.value in statuses:
        new_status = "active"
    elif statuses.issubset({ListingStatus.SOLD.value, ListingStatus.CANCELLED.value}):
        new_status = "cancelled" if ListingStatus.CANCELLED.value in statuses else "sold_out"
    else:
        return

    db.table("resale_campaigns").update({"status": new_status}).eq(
        "id", campaign_id
    ).execute()


def complete_resale_settlement(
    db: Any,
    payment_reference: str,
    ticket_id: str,
    buyer_wallet: Optional[str],
    listing_id: Optional[str] = None,
    currency: str = "ZAR",
) -> None:
    """Finalize resale payment: update ticket, rotate QR version, close listing/reservation, post ledger."""
    tx_resp = (
        db.table("transactions")
        .select("*")
        .eq("payment_reference", payment_reference)
        .execute()
    )
    tx = tx_resp.data[0] if tx_resp.data else {}
    resolved_listing_id = listing_id or tx.get("listing_id")

    ticket_resp = db.table("tickets").select("*").eq("id", ticket_id).execute()
    ticket = ticket_resp.data[0] if ticket_resp.data else {}
    previous_owner = ticket.get("owner_wallet")
    next_version = int(ticket.get("credential_version", 1)) + 1

    ticket_update: dict[str, Any] = {
        "status": TicketStatus.SOLD.value,
        "credential_version": next_version,
    }
    if buyer_wallet:
        ticket_update["owner_wallet"] = buyer_wallet

    db.table("tickets").update(ticket_update).eq("id", ticket_id).execute()

    db.table("transactions").update(
        {"status": TransactionStatus.SETTLED.value}
    ).eq("payment_reference", payment_reference).execute()

    # Complete any active reservation on this ticket
    db.table("ticket_reservations").update(
        {"status": ReservationStatus.COMPLETED.value}
    ).eq("ticket_id", ticket_id).execute()

    campaign_id: Optional[str] = None
    asking_price_zar = int(tx.get("amount") or ticket.get("original_price_zar") or 0)

    if resolved_listing_id:
        listing_resp = (
            db.table("resale_listings")
            .select("*")
            .eq("id", resolved_listing_id)
            .execute()
        )
        if listing_resp.data:
            listing = listing_resp.data[0]
            campaign_id = listing.get("campaign_id")
            asking_price_zar = int(listing.get("asking_price_zar", asking_price_zar))
            db.table("resale_listings").update(
                {"status": ListingStatus.SOLD.value}
            ).eq("id", resolved_listing_id).execute()
            sync_campaign_status(db, campaign_id)

    if currency == "ZAR" and asking_price_zar > 0:
        breakdown = calculate_resale_breakdown_zar(asking_price_zar)
        record_resale_ledger(
            db=db,
            payment_reference=payment_reference,
            gross_amount=breakdown.asking_price_zar,
            fee_amount=breakdown.marketplace_fee_zar,
            seller_amount=breakdown.seller_proceeds_zar,
            currency="ZAR",
        )
    elif currency == "USDC" and int(tx.get("amount") or 0) > 0:
        gross_micro = int(tx["amount"])
        fee_micro = (gross_micro * 500) // 10_000
        seller_micro = gross_micro - fee_micro
        record_resale_ledger(
            db=db,
            payment_reference=payment_reference,
            gross_amount=gross_micro,
            fee_amount=fee_micro,
            seller_amount=seller_micro,
            currency="USDC",
        )

    append_ownership_history(
        db=db,
        ticket_id=ticket_id,
        action="transferred",
        from_wallet=previous_owner,
        to_wallet=buyer_wallet,
        reference=payment_reference,
    )
    db.table("outbox_jobs").insert(
        {
            "job_type": "solana_devnet_transfer",
            "payload": {
                "ticket_id": ticket_id,
                "from_wallet": previous_owner,
                "to_wallet": buyer_wallet,
                "payment_reference": payment_reference,
            },
            "status": "queued",
        }
    ).execute()
    append_audit_log(
        db=db,
        actor=buyer_wallet or "payment_webhook",
        action="resale_settled",
        resource_type="ticket",
        resource_id=ticket_id,
        details={
            "payment_reference": payment_reference,
            "previous_owner": previous_owner,
            "new_owner": buyer_wallet,
            "credential_version": next_version,
        },
    )
