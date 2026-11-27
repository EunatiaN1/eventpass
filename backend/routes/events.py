"""Event management, organizer resale controls, and primary multi-ticket purchase routes."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import (
    AuthenticatedUser,
    get_current_user,
    require_organizer_or_admin,
)
from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.schemas.common import TicketStatus
from backend.schemas.events import (
    EventCreateRequest,
    EventResaleConfigUpdate,
    PrimaryPurchaseRequest,
)
from backend.services.credentials import issue_qr_credential
from backend.services.ledger import append_audit_log, append_ownership_history
from backend.services.pricing import evaluate_refund_window

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(db: Any = Depends(get_supabase_client)) -> List[Dict[str, Any]]:
    """List all events with live ticket counts and refund window metadata."""
    events_resp = db.table("events").select("*").execute()
    tickets_resp = db.table("tickets").select("id, event_id, status").execute()
    listings_resp = db.table("resale_listings").select("id, ticket_id, status").execute()

    tickets_by_event: Dict[str, List[Dict[str, Any]]] = {}
    ticket_event_map: Dict[str, str] = {}
    for t in tickets_resp.data or []:
        eid = t["event_id"]
        tickets_by_event.setdefault(eid, []).append(t)
        ticket_event_map[t["id"]] = eid

    active_resale_by_event: Dict[str, int] = {}
    for lst in listings_resp.data or []:
        if lst.get("status") == "active":
            eid = ticket_event_map.get(lst["ticket_id"], "")
            active_resale_by_event[eid] = active_resale_by_event.get(eid, 0) + 1

    enriched: List[Dict[str, Any]] = []
    for ev in events_resp.data or []:
        eid = ev["id"]
        ev_tickets = tickets_by_event.get(eid, [])
        refund_info = evaluate_refund_window(ev)
        enriched.append(
            {
                **ev,
                "issued_tickets_count": len(ev_tickets),
                "active_resale_count": active_resale_by_event.get(eid, 0),
                "checked_in_count": sum(
                    1 for t in ev_tickets if t.get("status") == TicketStatus.CHECKED_IN.value
                ),
                "refund_window": {
                    "eligible": refund_info.eligible,
                    "reason": refund_info.reason,
                    "cutoff_at_local": refund_info.cutoff_at_local,
                    "timezone": refund_info.event_timezone,
                },
            }
        )
    return enriched


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreateRequest,
    _organizer: AuthenticatedUser = Depends(require_organizer_or_admin),
    db: Any = Depends(get_supabase_client),
) -> Dict[str, Any]:
    """Create a new event with organizer resale and 15-day refund window policy."""
    now = datetime.now(timezone.utc)
    event_id = f"evt-{uuid.uuid4().hex[:8]}"
    row = {
        "id": event_id,
        "title": payload.title,
        "venue": payload.venue,
        "event_date": payload.event_date,
        "timezone": payload.timezone,
        "organizer_wallet": payload.organizer_wallet,
        "ticket_price_zar": payload.ticket_price_zar,
        "resale_enabled": payload.resale_enabled,
        "max_resale_price_zar": payload.max_resale_price_zar,
        "max_resale_markup_bps": payload.max_resale_markup_bps,
        "marketplace_fee_bps": 500,
        "resale_start_at": now.isoformat(),
        "refund_window_open_at": payload.refund_window_open_at or now.isoformat(),
        "refund_cutoff_days": 15,
        "created_at": now.isoformat(),
    }
    resp = db.table("events").insert(row).execute()
    append_audit_log(
        db,
        actor=payload.organizer_wallet,
        action="event_created",
        resource_type="event",
        resource_id=event_id,
        details={"title": payload.title, "ticket_price_zar": payload.ticket_price_zar},
    )
    return resp.data[0]


@router.patch("/{event_id}/resale-config")
async def update_resale_config(
    event_id: str,
    payload: EventResaleConfigUpdate,
    _organizer: AuthenticatedUser = Depends(require_organizer_or_admin),
    db: Any = Depends(get_supabase_client),
) -> Dict[str, Any]:
    """Update organizer resale settings (toggle resale, price cap, markup, cutoff)."""
    ev_resp = db.table("events").select("*").eq("id", event_id).execute()
    if not ev_resp.data:
        raise HTTPException(status_code=404, detail="Event not found.")

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return ev_resp.data[0]

    updated = db.table("events").update(updates).eq("id", event_id).execute()
    append_audit_log(
        db,
        actor=ev_resp.data[0].get("organizer_wallet", "organizer"),
        action="resale_config_updated",
        resource_type="event",
        resource_id=event_id,
        details=updates,
    )
    return updated.data[0]


@router.post("/{event_id}/purchase-primary", status_code=status.HTTP_201_CREATED)
async def purchase_primary_tickets(
    event_id: str,
    payload: PrimaryPurchaseRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Any = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Primary checkout: creates N individually identifiable Metaplex Core ticket records."""
    if payload.buyer_wallet != current_user.wallet and current_user.role not in ("organizer", "admin"):
        raise HTTPException(
            status_code=403, detail="buyer_wallet must match authenticated user."
        )
    ev_resp = db.table("events").select("*").eq("id", event_id).execute()
    if not ev_resp.data:
        raise HTTPException(status_code=404, detail="Event not found.")

    event = ev_resp.data[0]
    unit_price = int(event.get("ticket_price_zar", 500))
    total_zar = unit_price * payload.quantity
    order_ref = f"ord-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()

    created_tickets: List[Dict[str, Any]] = []
    for idx in range(payload.quantity):
        ticket_id = f"tkt-{uuid.uuid4().hex[:8]}"
        asset_addr = f"CoreAsset{uuid.uuid4().hex[:12]}Devnet"
        ticket_row = {
            "id": ticket_id,
            "event_id": event_id,
            "asset_address": asset_addr,
            "owner_wallet": payload.buyer_wallet,
            "original_buyer_wallet": payload.buyer_wallet,
            "order_reference": order_ref,
            "tier": payload.tier,
            "status": TicketStatus.ISSUED.value,
            "original_price_zar": unit_price,
            "credential_version": 1,
            "checked_in_at": None,
            "created_at": now,
        }
        db.table("tickets").insert(ticket_row).execute()
        append_ownership_history(
            db,
            ticket_id=ticket_id,
            action="issued",
            from_wallet=event.get("organizer_wallet"),
            to_wallet=payload.buyer_wallet,
            reference=order_ref,
        )
        qr_token = issue_qr_credential(ticket_row, settings)
        created_tickets.append({**ticket_row, "qr_token": qr_token, "unit_index": idx + 1})

    db.table("transactions").insert(
        {
            "id": str(uuid.uuid4()),
            "payment_reference": order_ref,
            "provider": "paystack" if payload.payment_method == "card" else "payfast",
            "payment_method": payload.payment_method,
            "amount": total_zar,
            "currency": "ZAR",
            "status": "settled",
            "ticket_id": created_tickets[0]["id"],
            "buyer_wallet": payload.buyer_wallet,
            "created_at": now,
        }
    ).execute()

    return {
        "order_reference": order_ref,
        "event_id": event_id,
        "quantity": payload.quantity,
        "total_zar": total_zar,
        "tickets": created_tickets,
    }


@router.get("/{event_id}/analytics")
async def get_event_analytics(
    event_id: str,
    _organizer: AuthenticatedUser = Depends(require_organizer_or_admin),
    db: Any = Depends(get_supabase_client),
) -> Dict[str, Any]:
    """Organizer analytics summary: primary tickets, resale volume, check-ins, refunds."""
    ev_resp = db.table("events").select("*").eq("id", event_id).execute()
    if not ev_resp.data:
        raise HTTPException(status_code=404, detail="Event not found.")
    event = ev_resp.data[0]

    tickets = db.table("tickets").select("*").eq("event_id", event_id).execute().data or []
    ticket_ids = {t["id"] for t in tickets}
    listings = [
        l for l in (db.table("resale_listings").select("*").execute().data or [])
        if l.get("ticket_id") in ticket_ids
    ]
    refunds = [
        r for r in (db.table("refund_requests").select("*").execute().data or [])
        if r.get("ticket_id") in ticket_ids
    ]

    return {
        "event": event,
        "total_tickets": len(tickets),
        "by_status": {
            "issued": sum(1 for t in tickets if t.get("status") == "issued"),
            "listed": sum(1 for t in tickets if t.get("status") == "listed"),
            "reserved": sum(1 for t in tickets if t.get("status") == "reserved"),
            "sold": sum(1 for t in tickets if t.get("status") == "sold"),
            "refunded": sum(1 for t in tickets if t.get("status") == "refunded"),
            "checked_in": sum(1 for t in tickets if t.get("status") == "checked_in"),
        },
        "resale_listings_total": len(listings),
        "resale_listings_sold": sum(1 for l in listings if l.get("status") == "sold"),
        "refunds_count": len(refunds),
        "refunds_total_zar": sum(int(r.get("refund_amount_zar", 0)) for r in refunds),
    }
