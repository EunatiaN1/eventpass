"""Immutable double-entry ledger, audit logging, and ownership history helpers."""

from typing import Any, Dict, List, Optional, Tuple
import uuid


def post_balanced_journal(
    db: Any,
    reference: str,
    description: str,
    currency: str,
    lines: List[Tuple[str, str, int]],
) -> Optional[Dict[str, Any]]:
    """Post a balanced double-entry journal (debits must equal credits).

    Idempotent on `reference`. Returns the created or existing journal row.
    """
    debit_total = sum(amt for _, direction, amt in lines if direction == "debit")
    credit_total = sum(amt for _, direction, amt in lines if direction == "credit")
    if debit_total != credit_total or debit_total < 0:
        raise ValueError(
            f"Unbalanced ledger journal {reference}: debits={debit_total}, credits={credit_total}"
        )

    existing = (
        db.table("ledger_journals").select("*").eq("reference", reference).execute()
    )
    if existing.data:
        return existing.data[0]

    journal_id = str(uuid.uuid4())
    journal_resp = (
        db.table("ledger_journals")
        .insert(
            {
                "id": journal_id,
                "reference": reference,
                "description": description,
                "currency": currency,
            }
        )
        .execute()
    )
    journal = journal_resp.data[0]

    for account_code, direction, amount in lines:
        db.table("ledger_entries").insert(
            {
                "id": str(uuid.uuid4()),
                "journal_id": journal_id,
                "account_code": account_code,
                "direction": direction,
                "amount": int(amount),
            }
        ).execute()

    return journal


def record_resale_ledger(
    db: Any,
    payment_reference: str,
    gross_amount: int,
    fee_amount: int,
    seller_amount: int,
    currency: str = "ZAR",
) -> None:
    """Post double-entry journal for verified resale payment capture (95% seller / 5% fee)."""
    post_balanced_journal(
        db=db,
        reference=f"jrn_resale_{payment_reference}",
        description=f"Resale settlement {payment_reference} (5% EventPass fee / 95% seller)",
        currency=currency,
        lines=[
            ("1010", "debit", gross_amount),
            ("2010", "credit", seller_amount),
            ("4010", "credit", fee_amount),
        ],
    )


def record_refund_ledger(
    db: Any,
    refund_id: str,
    original_price_zar: int,
    refund_amount_zar: int,
    retained_amount_zar: int,
) -> None:
    """Post double-entry journal for 75% unsold-ticket refund (75% buyer / 25% retained)."""
    post_balanced_journal(
        db=db,
        reference=f"jrn_refund_{refund_id}",
        description=f"Unsold-ticket 75% refund {refund_id} (25% retained)",
        currency="ZAR",
        lines=[
            ("5010", "debit", original_price_zar),
            ("2020", "credit", refund_amount_zar),
            ("4020", "credit", retained_amount_zar),
        ],
    )


def append_ownership_history(
    db: Any,
    ticket_id: str,
    action: str,
    from_wallet: Optional[str],
    to_wallet: Optional[str],
    reference: str,
) -> None:
    """Append an immutable ownership transition record."""
    db.table("ticket_ownership_history").insert(
        {
            "ticket_id": ticket_id,
            "from_wallet": from_wallet,
            "to_wallet": to_wallet,
            "action": action,
            "reference": reference,
        }
    ).execute()


def append_audit_log(
    db: Any,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a security-sensitive audit event."""
    db.table("audit_logs").insert(
        {
            "actor": actor,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
        }
    ).execute()
