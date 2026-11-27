"""Social resale campaigns, individual listings, atomic reservations, and unified checkout."""

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Dict, List
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from backend.database import get_supabase_client
from backend.schemas.campaigns import (
    CampaignCreateRequest,
    CheckoutConfirmDemoRequest,
    CheckoutInitiateRequest,
    ListingCancelRequest,
    ListingReserveRequest,
)
from backend.schemas.common import (
    ListingStatus,
    ReservationStatus,
    TicketStatus,
    TransactionStatus,
)
from backend.services.ledger import append_audit_log
from backend.services.pricing import (
    calculate_resale_breakdown_zar,
    validate_resale_price_cap,
)
from backend.services.settlement import complete_resale_settlement, sync_campaign_status
from backend.services.solana import finalize_solana_transfer

router = APIRouter(tags=["campaigns & checkout"])


def _release_expired_reservations(db: Any) -> None:
    """Release any reservations whose expires_at timestamp has passed."""
    now = datetime.now(timezone.utc)
    rows = db.table("ticket_reservations").select("*").execute().data or []
    for res in rows:
        if res.get("status") != ReservationStatus.ACTIVE.value:
            continue
        exp = datetime.fromisoformat(res["expires_at"].replace("Z", "+00:00"))
        if exp <= now:
            db.table("ticket_reservations").update(
                {"status": ReservationStatus.EXPIRED.value}
            ).eq("id", res["id"]).execute()
            tid = res["ticket_id"]
            db.table("tickets").update({"status": TicketStatus.LISTED.value}).eq(
                "id", tid
            ).execute()
            for lst in (
                db.table("resale_listings").select("*").eq("ticket_id", tid).execute().data
                or []
            ):
                if lst.get("status") == ListingStatus.RESERVED.value:
                    db.table("resale_listings").update(
                        {"status": ListingStatus.ACTIVE.value}
                    ).eq("id", lst["id"]).execute()


@router.get("/api/campaigns")
async def list_campaigns(db: Any = Depends(get_supabase_client)) -> List[Dict[str, Any]]:
    """List all social resale campaigns with live availability counts."""
    _release_expired_reservations(db)
    campaigns = db.table("resale_campaigns").select("*").execute().data or []
    events = {e["id"]: e for e in (db.table("events").select("*").execute().data or [])}
    listings = db.table("resale_listings").select("*").execute().data or []

    listings_by_cmp: Dict[str, List[Dict[str, Any]]] = {}
    for l in listings:
        if l.get("campaign_id"):
            listings_by_cmp.setdefault(l["campaign_id"], []).append(l)

    result: List[Dict[str, Any]] = []
    for cmp in campaigns:
        cmp_listings = listings_by_cmp.get(cmp["id"], [])
        ev = events.get(cmp["event_id"], {})
        available = sum(1 for l in cmp_listings if l.get("status") == ListingStatus.ACTIVE.value)
        reserved = sum(1 for l in cmp_listings if l.get("status") == ListingStatus.RESERVED.value)
        sold = sum(1 for l in cmp_listings if l.get("status") == ListingStatus.SOLD.value)
        result.append(
            {
                **cmp,
                "event_title": ev.get("title", "Unknown Event"),
                "event_date": ev.get("event_date"),
                "event_venue": ev.get("venue"),
                "total_count": len(cmp_listings),
                "available_count": available,
                "reserved_count": reserved,
                "sold_count": sold,
                "share_path": f"/c/{cmp['slug']}",
            }
        )
    return result


@router.post("/api/campaigns", status_code=status.HTTP_201_CREATED)
async def create_resale_campaign(
    payload: CampaignCreateRequest, db: Any = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Create individual resale listings for selected tickets grouped under one shareable campaign."""
    lock_ctx = db.lock if hasattr(db, "lock") else nullcontext()
    with lock_ctx:
        events = {e["id"]: e for e in (db.table("events").select("*").execute().data or [])}
        existing_listings = db.table("resale_listings").select("*").execute().data or []

        validated_items = []
        event_ids = set()

        for item in payload.items:
            t_resp = db.table("tickets").select("*").eq("id", item.ticket_id).execute()
            if not t_resp.data:
                raise HTTPException(status_code=404, detail=f"Ticket {item.ticket_id} not found.")
            ticket = t_resp.data[0]
            event_ids.add(ticket["event_id"])

            if ticket.get("owner_wallet") != payload.seller_wallet:
                raise HTTPException(
                    status_code=403, detail=f"Seller does not own ticket {item.ticket_id}."
                )
            if ticket.get("status") != TicketStatus.ISSUED.value:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ticket {item.ticket_id} is not eligible (status={ticket.get('status')}).",
                )

            if any(
                l["ticket_id"] == item.ticket_id
                and l.get("status") in (ListingStatus.ACTIVE.value, ListingStatus.RESERVED.value)
                for l in existing_listings
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"Ticket {item.ticket_id} already has an active listing.",
                )

            event = events.get(ticket["event_id"])
            if not event:
                raise HTTPException(status_code=404, detail="Event not found.")
            if not event.get("resale_enabled", False):
                raise HTTPException(
                    status_code=409, detail="Resale is currently disabled by the organizer."
                )

            cap_err = validate_resale_price_cap(
                item.asking_price_zar, int(ticket["original_price_zar"]), event
            )
            if cap_err:
                raise HTTPException(status_code=422, detail=cap_err)

            validated_items.append((ticket, item.asking_price_zar))

        if len(event_ids) != 1:
            raise HTTPException(
                status_code=422, detail="All tickets in one campaign must belong to the same event."
            )

        event_id = next(iter(event_ids))
        campaign_id = f"cmp-{uuid.uuid4().hex[:8]}"
        slug = f"ep-{secrets.token_urlsafe(6).lower()}"
        now = datetime.now(timezone.utc).isoformat()

        campaign_row = {
            "id": campaign_id,
            "slug": slug,
            "event_id": event_id,
            "seller_wallet": payload.seller_wallet,
            "title": payload.title,
            "status": "active",
            "created_at": now,
        }
        db.table("resale_campaigns").insert(campaign_row).execute()

        created_listings: List[Dict[str, Any]] = []
        for ticket, asking_price in validated_items:
            listing_id = f"lst-{uuid.uuid4().hex[:8]}"
            listing_row = {
                "id": listing_id,
                "campaign_id": campaign_id,
                "ticket_id": ticket["id"],
                "seller_wallet": payload.seller_wallet,
                "asking_price_zar": asking_price,
                "status": ListingStatus.ACTIVE.value,
                "created_at": now,
            }
            db.table("resale_listings").insert(listing_row).execute()
            db.table("tickets").update({"status": TicketStatus.LISTED.value}).eq(
                "id", ticket["id"]
            ).execute()
            breakdown = calculate_resale_breakdown_zar(asking_price)
            created_listings.append(
                {
                    **listing_row,
                    "marketplace_fee_zar": breakdown.marketplace_fee_zar,
                    "seller_proceeds_zar": breakdown.seller_proceeds_zar,
                }
            )

        append_audit_log(
            db,
            actor=payload.seller_wallet,
            action="resale_campaign_created",
            resource_type="campaign",
            resource_id=campaign_id,
            details={"slug": slug, "ticket_count": len(created_listings)},
        )

        return {
            **campaign_row,
            "share_path": f"/c/{slug}",
            "listings": created_listings,
        }


@router.get("/api/campaigns/{slug}")
async def get_public_campaign(
    slug: str, db: Any = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Public campaign view (shared between marketplace and social links; never exposes QR tokens)."""
    _release_expired_reservations(db)
    cmp_resp = db.table("resale_campaigns").select("*").eq("slug", slug).execute()
    if not cmp_resp.data:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    campaign = cmp_resp.data[0]

    ev_resp = db.table("events").select("*").eq("id", campaign["event_id"]).execute()
    event = ev_resp.data[0] if ev_resp.data else {}

    listings = (
        db.table("resale_listings").select("*").eq("campaign_id", campaign["id"]).execute().data
        or []
    )
    tickets_map = {
        t["id"]: t for t in (db.table("tickets").select("*").execute().data or [])
    }
    reservations_map = {
        r["ticket_id"]: r
        for r in (db.table("ticket_reservations").select("*").execute().data or [])
        if r.get("status") == ReservationStatus.ACTIVE.value
    }

    enriched_listings: List[Dict[str, Any]] = []
    for l in listings:
        t = tickets_map.get(l["ticket_id"], {})
        breakdown = calculate_resale_breakdown_zar(int(l["asking_price_zar"]))
        res = reservations_map.get(l["ticket_id"])
        enriched_listings.append(
            {
                "id": l["id"],
                "ticket_id": l["ticket_id"],
                "tier": t.get("tier", "General Admission"),
                "asset_address": t.get("asset_address"),
                "original_price_zar": t.get("original_price_zar"),
                "asking_price_zar": l["asking_price_zar"],
                "marketplace_fee_zar": breakdown.marketplace_fee_zar,
                "seller_proceeds_zar": breakdown.seller_proceeds_zar,
                "status": l["status"],
                "reserved_until": res.get("expires_at") if res else None,
            }
        )

    available_count = sum(
        1 for l in enriched_listings if l["status"] == ListingStatus.ACTIVE.value
    )

    return {
        "campaign": campaign,
        "event": {
            "id": event.get("id"),
            "title": event.get("title"),
            "venue": event.get("venue"),
            "event_date": event.get("event_date"),
            "timezone": event.get("timezone"),
            "resale_enabled": event.get("resale_enabled", True),
            "max_resale_price_zar": event.get("max_resale_price_zar"),
        },
        "available_count": available_count,
        "total_count": len(enriched_listings),
        "listings": enriched_listings,
    }


@router.post("/api/listings/{listing_id}/cancel")
async def cancel_listing(
    listing_id: str,
    payload: ListingCancelRequest,
    db: Any = Depends(get_supabase_client),
) -> Dict[str, Any]:
    """Allow seller to cancel an active listing (blocked if currently reserved or sold)."""
    lock_ctx = db.lock if hasattr(db, "lock") else nullcontext()
    with lock_ctx:
        l_resp = db.table("resale_listings").select("*").eq("id", listing_id).execute()
        if not l_resp.data:
            raise HTTPException(status_code=404, detail="Listing not found.")
        listing = l_resp.data[0]

        if listing.get("seller_wallet") != payload.seller_wallet:
            raise HTTPException(status_code=403, detail="Only the seller can cancel this listing.")
        if listing.get("status") != ListingStatus.ACTIVE.value:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot cancel listing in status '{listing.get('status')}'.",
            )

        db.table("resale_listings").update({"status": ListingStatus.CANCELLED.value}).eq(
            "id", listing_id
        ).execute()
        db.table("tickets").update({"status": TicketStatus.ISSUED.value}).eq(
            "id", listing["ticket_id"]
        ).execute()
        sync_campaign_status(db, listing.get("campaign_id"))
        return {"status": "cancelled", "listing_id": listing_id}


@router.post("/api/listings/{listing_id}/reserve")
async def reserve_listing(
    listing_id: str,
    payload: ListingReserveRequest,
    db: Any = Depends(get_supabase_client),
) -> Dict[str, Any]:
    """Atomically reserve a listing for a buyer checkout attempt."""
    lock_ctx = db.lock if hasattr(db, "lock") else nullcontext()
    with lock_ctx:
        _release_expired_reservations(db)
        l_resp = db.table("resale_listings").select("*").eq("id", listing_id).execute()
        if not l_resp.data:
            raise HTTPException(status_code=404, detail="Listing not found.")
        listing = l_resp.data[0]

        if listing.get("status") != ListingStatus.ACTIVE.value:
            raise HTTPException(
                status_code=409,
                detail=f"Listing is not available (status={listing.get('status')}).",
            )

        ticket_id = listing["ticket_id"]
        if listing.get("seller_wallet") == payload.buyer_wallet:
            raise HTTPException(
                status_code=422, detail="Seller cannot reserve their own listing."
            )

        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(seconds=payload.ttl_seconds)).isoformat()

        # Replace any non-active historical reservation row for this ticket_id
        existing_res = (
            db.table("ticket_reservations").select("*").eq("ticket_id", ticket_id).execute().data
            or []
        )
        if existing_res:
            if existing_res[0].get("status") == ReservationStatus.ACTIVE.value:
                raise HTTPException(
                    status_code=409, detail="Ticket is already reserved by another buyer."
                )
            reservation_id = existing_res[0]["id"]
            db.table("ticket_reservations").update(
                {
                    "buyer_wallet": payload.buyer_wallet,
                    "status": ReservationStatus.ACTIVE.value,
                    "expires_at": expires_at,
                }
            ).eq("id", reservation_id).execute()
        else:
            reservation_id = f"res-{uuid.uuid4().hex[:8]}"
            db.table("ticket_reservations").insert(
                {
                    "id": reservation_id,
                    "ticket_id": ticket_id,
                    "buyer_wallet": payload.buyer_wallet,
                    "status": ReservationStatus.ACTIVE.value,
                    "expires_at": expires_at,
                    "created_at": now.isoformat(),
                }
            ).execute()

        db.table("resale_listings").update({"status": ListingStatus.RESERVED.value}).eq(
            "id", listing_id
        ).execute()
        db.table("tickets").update({"status": TicketStatus.RESERVED.value}).eq(
            "id", ticket_id
        ).execute()

        return {
            "reservation_id": reservation_id,
            "listing_id": listing_id,
            "ticket_id": ticket_id,
            "buyer_wallet": payload.buyer_wallet,
            "status": ReservationStatus.ACTIVE.value,
            "expires_at": expires_at,
        }


@router.post("/api/checkout/initiate")
async def initiate_checkout(
    payload: CheckoutInitiateRequest, db: Any = Depends(get_supabase_client)
) -> Dict[str, Any]:
    """Initiate unified on-platform checkout (Wallet, Card, EFT, PayFast, Payflex, or x402)."""
    reserve_res = await reserve_listing(
        payload.listing_id,
        ListingReserveRequest(buyer_wallet=payload.buyer_wallet),
        db=db,
    )
    listing = (
        db.table("resale_listings").select("*").eq("id", payload.listing_id).execute().data[0]
    )
    asking_price = int(listing["asking_price_zar"])
    breakdown = calculate_resale_breakdown_zar(asking_price)
    payment_ref = f"epay_{secrets.token_hex(6)}"

    provider = (
        "payfast"
        if payload.payment_method in ("payfast", "eft", "eventpass_wallet")
        else ("x402" if payload.payment_method == "x402" else "paystack")
    )

    tx_row = {
        "id": str(uuid.uuid4()),
        "payment_reference": payment_ref,
        "provider": provider,
        "payment_method": payload.payment_method,
        "amount": asking_price,
        "currency": "ZAR",
        "marketplace_fee_amount": breakdown.marketplace_fee_zar,
        "seller_proceeds_amount": breakdown.seller_proceeds_zar,
        "status": TransactionStatus.PENDING.value,
        "ticket_id": listing["ticket_id"],
        "listing_id": payload.listing_id,
        "buyer_wallet": payload.buyer_wallet,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.table("transactions").insert(tx_row).execute()

    instructions: Dict[str, Any] = {
        "method": payload.payment_method,
        "note": "Payment remains pending until verified server-to-server.",
    }
    if payload.payment_method == "eft":
        instructions["eft_bank_details"] = {
            "bank": "First National Bank (FNB)",
            "account_name": "EventPass Marketplace Clearing (Dev Sandbox)",
            "account_number": "62000000000",
            "branch_code": "250655",
            "reference": payment_ref,
            "amount_zar": asking_price,
            "warning": "Use the exact reference above. Screenshots are not proof of cleared funds.",
        }
    elif payload.payment_method == "payflex":
        instalment = asking_price // 4
        instructions["payflex_schedule"] = {
            "instalments": 4,
            "per_fortnight_zar": instalment,
            "interest_free": True,
        }

    return {
        "payment_reference": payment_ref,
        "status": TransactionStatus.PENDING.value,
        "listing_id": payload.listing_id,
        "ticket_id": listing["ticket_id"],
        "reservation": reserve_res,
        "pricing": {
            "ticket_resale_price_zar": breakdown.asking_price_zar,
            "marketplace_fee_zar_5pct": breakdown.marketplace_fee_zar,
            "seller_proceeds_zar_95pct": breakdown.seller_proceeds_zar,
            "currency": "ZAR",
        },
        "instructions": instructions,
    }


@router.post("/api/checkout/confirm-demo")
async def confirm_demo_checkout(
    payload: CheckoutConfirmDemoRequest,
    background_tasks: BackgroundTasks,
    db: Any = Depends(get_supabase_client),
) -> Dict[str, Any]:
    """Dev-mode settlement simulator (runs the same atomic settlement, QR rotation & ledger)."""
    lock_ctx = db.lock if hasattr(db, "lock") else nullcontext()
    with lock_ctx:
        tx_resp = (
            db.table("transactions")
            .select("*")
            .eq("payment_reference", payload.payment_reference)
            .execute()
        )
        if not tx_resp.data:
            raise HTTPException(status_code=404, detail="Transaction not found.")
        tx = tx_resp.data[0]

        if tx.get("status") == TransactionStatus.SETTLED.value:
            return {
                "status": "already_settled",
                "idempotent": True,
                "payment_reference": payload.payment_reference,
                "ticket_id": tx.get("ticket_id"),
            }

        ticket_id = tx.get("ticket_id")
        listing_id = tx.get("listing_id")

        if payload.simulate_outcome == "failed":
            db.table("transactions").update({"status": TransactionStatus.FAILED.value}).eq(
                "payment_reference", payload.payment_reference
            ).execute()
            if ticket_id:
                db.table("ticket_reservations").update(
                    {"status": ReservationStatus.CANCELLED.value}
                ).eq("ticket_id", ticket_id).execute()
                db.table("tickets").update({"status": TicketStatus.LISTED.value}).eq(
                    "id", ticket_id
                ).execute()
            if listing_id:
                db.table("resale_listings").update({"status": ListingStatus.ACTIVE.value}).eq(
                    "id", listing_id
                ).execute()
            return {
                "status": "failed",
                "payment_reference": payload.payment_reference,
                "ticket_id": ticket_id,
                "message": "Payment failed; reservation released and ticket returned to live inventory.",
            }

        complete_resale_settlement(
            db=db,
            payment_reference=payload.payment_reference,
            ticket_id=ticket_id,
            buyer_wallet=tx.get("buyer_wallet"),
            listing_id=listing_id,
            currency=tx.get("currency", "ZAR"),
        )
        background_tasks.add_task(finalize_solana_transfer, ticket_id, tx.get("buyer_wallet"))

        return {
            "status": "settled",
            "idempotent": False,
            "payment_reference": payload.payment_reference,
            "ticket_id": ticket_id,
            "buyer_wallet": tx.get("buyer_wallet"),
            "message": "Payment verified, ticket ownership transferred, seller QR revoked & new QR issued.",
        }
