"""Individual ticket views, signed QR credentials, and 75% unsold-ticket refunds."""

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth import AuthenticatedUser, get_current_user
from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.schemas.common import ListingStatus, TicketStatus
from backend.schemas.tickets import RefundRequestCreate, RefundResponse, TicketCredentialResponse
from backend.services.credentials import issue_qr_credential
from backend.services.ledger import (
    append_audit_log,
    append_ownership_history,
    record_refund_ledger,
)
from backend.services.pricing import (
    calculate_unsold_refund_zar,
    evaluate_refund_window,
)
from backend.services.settlement import sync_campaign_status

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _add_business_days(start: datetime, days: int) -> datetime:
    """Calculate target payout date N business days ahead (Mon-Fri)."""
    cur = start
    added = 0
    while added < days:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur


@router.get("")
async def list_tickets(
    owner_wallet: Optional[str] = Query(default=None),
    event_id: Optional[str] = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Any = Depends(get_supabase_client),
) -> List[Dict[str, Any]]:
    """Return tickets individually with event, listing, reservation, and refund eligibility details."""
    effective_owner = owner_wallet
    if current_user.role not in ("organizer", "admin"):
        effective_owner = current_user.wallet
    query = db.table("tickets").select("*")
    if effective_owner:
        query = query.eq("owner_wallet", effective_owner)
    if event_id:
        query = query.eq("event_id", event_id)
    tickets = query.execute().data or []

    events = {e["id"]: e for e in (db.table("events").select("*").execute().data or [])}
    listings = db.table("resale_listings").select("*").execute().data or []
    active_listing_by_ticket = {
        l["ticket_id"]: l
        for l in listings
        if l.get("status") in (ListingStatus.ACTIVE.value, ListingStatus.RESERVED.value)
    }

    enriched: List[Dict[str, Any]] = []
    for t in tickets:
        ev = events.get(t["event_id"], {})
        refund_window = evaluate_refund_window(ev) if ev else None
        refund_calc = calculate_unsold_refund_zar(int(t.get("original_price_zar", 0)))
        can_refund = (
            t.get("status") in (TicketStatus.ISSUED.value, TicketStatus.LISTED.value)
            and t.get("owner_wallet") == (t.get("original_buyer_wallet") or t.get("owner_wallet"))
            and (refund_window.eligible if refund_window else False)
        )
        enriched.append(
            {
                **t,
                "event_title": ev.get("title", "Unknown Event"),
                "event_date": ev.get("event_date"),
                "event_venue": ev.get("venue"),
                "event_timezone": ev.get("timezone", "Africa/Johannesburg"),
                "resale_enabled": ev.get("resale_enabled", True),
                "max_resale_price_zar": ev.get("max_resale_price_zar"),
                "active_listing": active_listing_by_ticket.get(t["id"]),
                "refund_eligible": can_refund,
                "refund_amount_zar": refund_calc.refund_amount_zar,
                "refund_window_reason": None if can_refund else (
                    refund_window.reason if refund_window and not refund_window.eligible
                    else f"Ticket status '{t.get('status')}' is not eligible for unsold refund."
                ),
                "refund_cutoff_at_local": refund_window.cutoff_at_local if refund_window else None,
            }
        )
    return enriched


@router.get("/{ticket_id}/credential", response_model=TicketCredentialResponse)
async def get_ticket_credential(
    ticket_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Any = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> TicketCredentialResponse:
    """Issue/retrieve the live signed QR credential for a valid non-refunded ticket."""
    resp = db.table("tickets").select("*").eq("id", ticket_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    ticket = resp.data[0]
    if (
        ticket.get("owner_wallet") != current_user.wallet
        and current_user.role not in ("organizer", "admin")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the ticket owner can access this admission credential.",
        )
    if ticket.get("status") == TicketStatus.REFUNDED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ticket has been refunded; admission credential is permanently revoked.",
        )

    qr_token = issue_qr_credential(ticket, settings)
    return TicketCredentialResponse(
        ticket_id=ticket["id"],
        event_id=ticket["event_id"],
        credential_version=int(ticket.get("credential_version", 1)),
        status=ticket["status"],
        qr_token=qr_token,
        owner_wallet=ticket["owner_wallet"],
        asset_address=ticket["asset_address"],
    )


@router.post("/{ticket_id}/refund", response_model=RefundResponse)
async def request_unsold_ticket_refund(
    ticket_id: str,
    payload: RefundRequestCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Any = Depends(get_supabase_client),
) -> RefundResponse:
    """Execute a 75% unsold-ticket refund atomically (mutually exclusive with resale/sale)."""
    if (
        payload.requester_wallet != current_user.wallet
        and current_user.role not in ("organizer", "admin")
    ):
        raise HTTPException(
            status_code=403,
            detail="requester_wallet must match authenticated user.",
        )
    lock_ctx = db.lock if hasattr(db, "lock") else nullcontext()
    with lock_ctx:
        t_resp = db.table("tickets").select("*").eq("id", ticket_id).execute()
        if not t_resp.data:
            raise HTTPException(status_code=404, detail="Ticket not found.")
        ticket = t_resp.data[0]

        if ticket.get("owner_wallet") != payload.requester_wallet:
            raise HTTPException(
                status_code=403, detail="Only the current ticket owner may request a refund."
            )
        original_buyer = ticket.get("original_buyer_wallet")
        if original_buyer and original_buyer != payload.requester_wallet:
            raise HTTPException(
                status_code=403,
                detail="Only the original purchaser is eligible for the 75% unsold-ticket refund.",
            )

        if ticket.get("status") not in (TicketStatus.ISSUED.value, TicketStatus.LISTED.value):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot refund ticket in status '{ticket.get('status')}'.",
            )

        # Ensure no active reservation exists
        res_resp = db.table("ticket_reservations").select("*").eq("ticket_id", ticket_id).execute()
        for res in res_resp.data or []:
            if res.get("status") == "active":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ticket currently has an active buyer checkout reservation.",
                )

        ev_resp = db.table("events").select("*").eq("id", ticket["event_id"]).execute()
        if not ev_resp.data:
            raise HTTPException(status_code=404, detail="Associated event not found.")
        event = ev_resp.data[0]

        window_status = evaluate_refund_window(event)
        if not window_status.eligible:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=window_status.reason,
            )

        # Cancel any active listing for this ticket without closing remaining campaign tickets
        listings = (
            db.table("resale_listings").select("*").eq("ticket_id", ticket_id).execute().data
            or []
        )
        for lst in listings:
            if lst.get("status") == ListingStatus.ACTIVE.value:
                db.table("resale_listings").update(
                    {"status": ListingStatus.CANCELLED.value}
                ).eq("id", lst["id"]).execute()
                sync_campaign_status(db, lst.get("campaign_id"))

        breakdown = calculate_unsold_refund_zar(int(ticket["original_price_zar"]))
        next_version = int(ticket.get("credential_version", 1)) + 1
        now = datetime.now(timezone.utc)
        payout_due = _add_business_days(now, 3)
        refund_id = f"ref-{uuid.uuid4().hex[:10]}"

        db.table("tickets").update(
            {
                "status": TicketStatus.REFUNDED.value,
                "credential_version": next_version,
            }
        ).eq("id", ticket_id).execute()

        db.table("refund_requests").insert(
            {
                "id": refund_id,
                "ticket_id": ticket_id,
                "requester_wallet": payload.requester_wallet,
                "original_price_zar": breakdown.original_price_zar,
                "refund_amount_zar": breakdown.refund_amount_zar,
                "retained_amount_zar": breakdown.retained_amount_zar,
                "status": "approved",
                "payout_due_at": payout_due.isoformat(),
                "created_at": now.isoformat(),
            }
        ).execute()

        record_refund_ledger(
            db=db,
            refund_id=refund_id,
            original_price_zar=breakdown.original_price_zar,
            refund_amount_zar=breakdown.refund_amount_zar,
            retained_amount_zar=breakdown.retained_amount_zar,
        )
        append_ownership_history(
            db=db,
            ticket_id=ticket_id,
            action="refunded",
            from_wallet=payload.requester_wallet,
            to_wallet=None,
            reference=refund_id,
        )
        append_audit_log(
            db=db,
            actor=payload.requester_wallet,
            action="unsold_ticket_refund_approved",
            resource_type="ticket",
            resource_id=ticket_id,
            details={
                "refund_id": refund_id,
                "refund_amount_zar": breakdown.refund_amount_zar,
                "retained_amount_zar": breakdown.retained_amount_zar,
            },
        )

        return RefundResponse(
            refund_id=refund_id,
            ticket_id=ticket_id,
            original_price_zar=breakdown.original_price_zar,
            refund_amount_zar=breakdown.refund_amount_zar,
            retained_amount_zar=breakdown.retained_amount_zar,
            status="approved",
            payout_due_at=payout_due.isoformat(),
            credential_version=next_version,
            message=(
                f"75% refund of R{breakdown.refund_amount_zar} approved "
                f"(R{breakdown.retained_amount_zar} retained). Payout targeted within 3 business days."
            ),
        )
