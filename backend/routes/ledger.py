"""Financial ledger, refund payouts, ownership history, outbox, and audit log endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Depends

from backend.database import get_supabase_client

router = APIRouter(prefix="/api/ledger", tags=["ledger & audit"])


@router.get("")
async def get_ledger_overview(db: Any = Depends(get_supabase_client)) -> Dict[str, Any]:
    """Return double-entry journals, entries, refund payouts, outbox jobs, and audit trail."""
    accounts = db.table("ledger_accounts").select("*").execute().data or []
    journals = db.table("ledger_journals").select("*").execute().data or []
    entries = db.table("ledger_entries").select("*").execute().data or []
    refunds = db.table("refund_requests").select("*").execute().data or []
    transactions = db.table("transactions").select("*").execute().data or []
    outbox = db.table("outbox_jobs").select("*").execute().data or []
    audit_logs = db.table("audit_logs").select("*").execute().data or []
    ownership_history = (
        db.table("ticket_ownership_history").select("*").execute().data or []
    )

    return {
        "accounts": accounts,
        "journals": journals,
        "entries": entries,
        "refund_requests": refunds,
        "transactions": transactions,
        "outbox_jobs": outbox,
        "audit_logs": audit_logs,
        "ownership_history": ownership_history,
    }
