"""Gate staff QR validation and atomic single-use check-in routes."""

from contextlib import nullcontext
from datetime import datetime, timezone\nimport logging
from typing import Any, Dict, List
import uuid

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import AuthenticatedUser, get_current_user
from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.schemas.checkin import CheckInRequest, CheckInResponse
from backend.schemas.common import TicketStatus
from backend.services.credentials import verify_qr_credential
from backend.services.ledger import append_audit_log, append_ownership_history\nfrom backend.services.solana import check_in_ticket

router = APIRouter(tags=["check-in"])\nlogger = logging.getLogger(__name__)


@router.post("/api/check-in", response_model=CheckInResponse)
async def validate_and_check_in(
    payload: CheckInRequest,
    _user: AuthenticatedUser = Depends(get_current_user),
    db: Any = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> CheckInResponse:
    """Validate a signed QR credential and atomically check in the ticket once."""
    ok, claims, err = verify_qr_credential(payload.qr_token, settings)
    if not ok:
        return CheckInResponse(accepted=False, result="invalid_signature", reason=err)

    ticket_id = claims.get("tid")
    token_event_id = claims.get("eid")
    token_ver = int(claims.get("ver", 0))

    if token_event_id != payload.event_id:
        return CheckInResponse(
            accepted=False,
            result="wrong_event",
            reason="QR credential belongs to a different event.",
            ticket_id=ticket_id,
            event_id=token_event_id,
        )

    lock_ctx = db.lock if hasattr(db, "lock") else nullcontext()
    with lock_ctx:
        t_resp = db.table("tickets").select("*").eq("id", ticket_id).execute()
        if not t_resp.data:
            return CheckInResponse(
                accepted=False,
                result="not_found",
                reason="Ticket record does not exist.",
                ticket_id=ticket_id,
            )
        ticket = t_resp.data[0]

        if ticket.get("status") == TicketStatus.REFUNDED.value:
            return CheckInResponse(
                accepted=False,
                result="refunded",
                reason="Ticket has been refunded and cancelled.",
                ticket_id=ticket_id,
                event_id=ticket["event_id"],
            )

        if int(ticket.get("credential_version", 1)) != token_ver:
            return CheckInResponse(
                accepted=False,
                result="credential_revoked",
                reason=(
                    f"QR credential version v{token_ver} has been revoked "
                    f"(current valid version is v{ticket.get('credential_version')})."
                ),
                ticket_id=ticket_id,
                event_id=ticket["event_id"],
                credential_version=int(ticket.get("credential_version", 1)),
            )

        if ticket.get("status") == TicketStatus.CHECKED_IN.value:
            return CheckInResponse(
                accepted=False,
                result="already_checked_in",
                reason=f"Ticket was already checked in at {ticket.get('checked_in_at')}.",
                ticket_id=ticket_id,
                event_id=ticket["event_id"],
                owner_wallet=ticket.get("owner_wallet"),
                credential_version=token_ver,
            )

        try:
            await check_in_ticket(
                event_id=str(ticket["event_id"]),
                ticket_id=str(ticket_id),
                settings=settings,
            )
        except Exception as exc:
            logger.exception("Devnet check-in failed ticket_id=%s", ticket_id)
            raise HTTPException(
                status_code=503,
                detail="On-chain check-in failed; admission was not recorded.",
            ) from exc

        now = datetime.now(timezone.utc).isoformat()
        db.table("tickets").update(
            {
                "status": TicketStatus.CHECKED_IN.value,
                "checked_in_at": now,
            }
        ).eq("id", ticket_id).execute()

        db.table("check_ins").insert(
            {
                "id": str(uuid.uuid4()),
                "ticket_id": ticket_id,
                "event_id": payload.event_id,
                "credential_version": token_ver,
                "scanner_id": payload.scanner_id,
                "result": "accepted",
                "created_at": now,
            }
        ).execute()

        append_ownership_history(
            db,
            ticket_id=ticket_id,
            action="checked_in",
            from_wallet=ticket.get("owner_wallet"),
            to_wallet=ticket.get("owner_wallet"),
            reference=payload.scanner_id,
        )
        append_audit_log(
            db,
            actor=payload.scanner_id,
            action="ticket_checked_in",
            resource_type="ticket",
            resource_id=ticket_id,
            details={"event_id": payload.event_id, "credential_version": token_ver},
        )

        return CheckInResponse(
            accepted=True,
            result="accepted",
            reason="Valid admission credential — check-in recorded.",
            ticket_id=ticket_id,
            event_id=ticket["event_id"],
            owner_wallet=ticket.get("owner_wallet"),
            credential_version=token_ver,
        )


@router.get("/api/check-ins/{event_id}")
async def list_event_check_ins(
    event_id: str,
    _user: AuthenticatedUser = Depends(get_current_user),
    db: Any = Depends(get_supabase_client),
) -> List[Dict[str, Any]]:
    """List check-in log records for a given event."""
    return (
        db.table("check_ins").select("*").eq("event_id", event_id).execute().data or []
    )
