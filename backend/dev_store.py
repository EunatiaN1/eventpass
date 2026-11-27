"""Thread-safe in-memory Supabase-compatible store for local development & preview."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import threading
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class DevResponse:
    data: List[Dict[str, Any]]


class DevQueryBuilder:
    """Thread-safe fluent query builder mimicking supabase-py / PostgREST."""

    def __init__(self, rows: List[Dict[str, Any]], lock: threading.RLock) -> None:
        self._rows = rows
        self._lock = lock
        self._op: Optional[str] = None
        self._filters: List[tuple[str, str, Any]] = []
        self._payload: Any = None
        self._order_by: Optional[tuple[str, bool]] = None
        self._limit_count: Optional[int] = None

    def select(self, _columns: str = "*") -> "DevQueryBuilder":
        self._op = "select"
        return self

    def insert(self, payload: Dict[str, Any]) -> "DevQueryBuilder":
        self._op = "insert"
        row = dict(payload)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self._payload = row
        return self

    def update(self, payload: Dict[str, Any]) -> "DevQueryBuilder":
        self._op = "update"
        self._payload = dict(payload)
        return self

    def delete(self) -> "DevQueryBuilder":
        self._op = "delete"
        return self

    def eq(self, column: str, value: Any) -> "DevQueryBuilder":
        self._filters.append(("eq", column, value))
        return self

    def neq(self, column: str, value: Any) -> "DevQueryBuilder":
        self._filters.append(("neq", column, value))
        return self

    def in_(self, column: str, values: List[Any]) -> "DevQueryBuilder":
        self._filters.append(("in", column, set(values)))
        return self

    def order(self, column: str, desc: bool = False) -> "DevQueryBuilder":
        self._order_by = (column, desc)
        return self

    def limit(self, count: int) -> "DevQueryBuilder":
        self._limit_count = count
        return self

    def _matches(self, row: Dict[str, Any]) -> bool:
        for op, col, val in self._filters:
            row_val = row.get(col)
            if op == "eq" and row_val != val:
                return False
            if op == "neq" and row_val == val:
                return False
            if op == "in" and row_val not in val:
                return False
        return True

    def execute(self) -> DevResponse:
        with self._lock:
            if self._op == "select":
                matched = [dict(r) for r in self._rows if self._matches(r)]
                if self._order_by:
                    col, desc = self._order_by
                    matched.sort(key=lambda r: str(r.get(col, "")), reverse=desc)
                if self._limit_count is not None:
                    matched = matched[: self._limit_count]
                return DevResponse(data=matched)

            if self._op == "insert":
                self._rows.append(self._payload)
                return DevResponse(data=[dict(self._payload)])

            if self._op == "update":
                updated: List[Dict[str, Any]] = []
                for row in self._rows:
                    if self._matches(row):
                        row.update(self._payload)
                        updated.append(dict(row))
                return DevResponse(data=updated)

            if self._op == "delete":
                kept: List[Dict[str, Any]] = []
                deleted: List[Dict[str, Any]] = []
                for row in self._rows:
                    if self._matches(row):
                        deleted.append(dict(row))
                    else:
                        kept.append(row)
                self._rows[:] = kept
                return DevResponse(data=deleted)

            raise ValueError(f"Unsupported operation: {self._op}")


class DevSupabaseClient:
    """In-memory seeded database used automatically when .env uses placeholder Supabase keys."""

    def __init__(self, seed: bool = True) -> None:
        self._lock = threading.RLock()
        self.tables: Dict[str, List[Dict[str, Any]]] = {
            "profiles": [],
            "otp_challenges": [],
            "events": [],
            "tickets": [],
            "resale_campaigns": [],
            "resale_listings": [],
            "transactions": [],
            "ticket_reservations": [],
            "refund_requests": [],
            "ledger_accounts": [],
            "ledger_journals": [],
            "ledger_entries": [],
            "ticket_ownership_history": [],
            "check_ins": [],
            "outbox_jobs": [],
            "audit_logs": [],
        }
        if seed:
            self._seed_initial_data()

    @property
    def lock(self) -> threading.RLock:
        """Expose reentrant lock for atomic multi-table transitions."""
        return self._lock

    def table(self, name: str) -> DevQueryBuilder:
        with self._lock:
            if name not in self.tables:
                self.tables[name] = []
            return DevQueryBuilder(self.tables[name], self._lock)

    def _seed_initial_data(self) -> None:
        now = datetime.now(timezone.utc)
        event_1_date = now + timedelta(days=45)
        event_2_date = now + timedelta(days=28)
        event_3_date = now + timedelta(days=10)  # Inside 14-day cutoff to demonstrate refund lock

        event_1_id = "evt-ct-electronic-2026"
        event_2_id = "evt-afrofuture-jhb-2026"
        event_3_id = "evt-soweto-jazz-2026"

        self.tables["events"].extend(
            [
                {
                    "id": event_1_id,
                    "title": "Cape Town Electronic Music Festival",
                    "venue": "DHL Stadium, Green Point",
                    "event_date": event_1_date.isoformat(),
                    "timezone": "Africa/Johannesburg",
                    "organizer_wallet": "OrgWalletCapeTown111111111111111111111111",
                    "resale_enabled": True,
                    "ticket_price_zar": 500,
                    "max_resale_price_zar": 600,
                    "max_resale_markup_bps": 2000,
                    "marketplace_fee_bps": 500,
                    "resale_start_at": (now - timedelta(days=5)).isoformat(),
                    "resale_cutoff_at": (event_1_date - timedelta(hours=4)).isoformat(),
                    "refund_window_open_at": (now - timedelta(days=10)).isoformat(),
                    "refund_cutoff_days": 15,
                    "created_at": now.isoformat(),
                },
                {
                    "id": event_2_id,
                    "title": "AfroFuture Johannesburg",
                    "venue": "Constitution Hill, Johannesburg",
                    "event_date": event_2_date.isoformat(),
                    "timezone": "Africa/Johannesburg",
                    "organizer_wallet": "OrgWalletJoburg22222222222222222222222222",
                    "resale_enabled": True,
                    "ticket_price_zar": 1000,
                    "max_resale_price_zar": 1150,
                    "max_resale_markup_bps": 1500,
                    "marketplace_fee_bps": 500,
                    "resale_start_at": (now - timedelta(days=5)).isoformat(),
                    "resale_cutoff_at": (event_2_date - timedelta(hours=6)).isoformat(),
                    "refund_window_open_at": (now - timedelta(days=10)).isoformat(),
                    "refund_cutoff_days": 15,
                    "created_at": now.isoformat(),
                },
                {
                    "id": event_3_id,
                    "title": "Soweto Sunset Jazz Sessions",
                    "venue": "Vilakazi Street Amphitheatre, Soweto",
                    "event_date": event_3_date.isoformat(),
                    "timezone": "Africa/Johannesburg",
                    "organizer_wallet": "OrgWalletSoweto33333333333333333333333333",
                    "resale_enabled": True,
                    "ticket_price_zar": 400,
                    "max_resale_price_zar": 440,
                    "max_resale_markup_bps": 1000,
                    "marketplace_fee_bps": 500,
                    "resale_start_at": (now - timedelta(days=10)).isoformat(),
                    "resale_cutoff_at": (event_3_date - timedelta(hours=2)).isoformat(),
                    "refund_window_open_at": (now - timedelta(days=20)).isoformat(),
                    "refund_cutoff_days": 15,
                    "created_at": now.isoformat(),
                },
            ]
        )

        seller_wallet = "SellerWalletDemo11111111111111111111111111"
        buyer_wallet = "BuyerWalletDemo222222222222222222222222222"
        organizer_wallet = "OrgWalletCapeTown111111111111111111111111"

        self.tables["profiles"].extend(
            [
                {
                    "id": "usr-buyer-demo",
                    "wallet_address": buyer_wallet,
                    "email": "buyer@eventpass.co.za",
                    "role": "buyer",
                    "created_at": now.isoformat(),
                },
                {
                    "id": "usr-seller-demo",
                    "wallet_address": seller_wallet,
                    "email": "seller@eventpass.co.za",
                    "role": "buyer",
                    "created_at": now.isoformat(),
                },
                {
                    "id": "usr-org-ct",
                    "wallet_address": organizer_wallet,
                    "email": "organizer@eventpass.co.za",
                    "role": "organizer",
                    "created_at": now.isoformat(),
                },
            ]
        )

        # Seed seller with 4 individual tickets from one multi-ticket order (#1-#4),
        # 3 of which (#1, #2, #3) are listed in a single social resale campaign,
        # and #4 is retained in My Tickets (eligible for 75% refund or listing).
        self.tables["tickets"].extend(
            [
                {
                    "id": "tkt-ct-001",
                    "event_id": event_1_id,
                    "asset_address": "CoreAssetCTEMF001Devnet1111111111111111111",
                    "owner_wallet": seller_wallet,
                    "original_buyer_wallet": seller_wallet,
                    "order_reference": "ord-seed-ct-01",
                    "tier": "General Admission",
                    "status": "listed",
                    "original_price_zar": 500,
                    "credential_version": 1,
                    "checked_in_at": None,
                    "created_at": now.isoformat(),
                },
                {
                    "id": "tkt-ct-002",
                    "event_id": event_1_id,
                    "asset_address": "CoreAssetCTEMF002Devnet1111111111111111111",
                    "owner_wallet": seller_wallet,
                    "original_buyer_wallet": seller_wallet,
                    "order_reference": "ord-seed-ct-01",
                    "tier": "General Admission",
                    "status": "listed",
                    "original_price_zar": 500,
                    "credential_version": 1,
                    "checked_in_at": None,
                    "created_at": now.isoformat(),
                },
                {
                    "id": "tkt-ct-003",
                    "event_id": event_1_id,
                    "asset_address": "CoreAssetCTEMF003Devnet1111111111111111111",
                    "owner_wallet": seller_wallet,
                    "original_buyer_wallet": seller_wallet,
                    "order_reference": "ord-seed-ct-01",
                    "tier": "General Admission",
                    "status": "listed",
                    "original_price_zar": 500,
                    "credential_version": 1,
                    "checked_in_at": None,
                    "created_at": now.isoformat(),
                },
                {
                    "id": "tkt-ct-004",
                    "event_id": event_1_id,
                    "asset_address": "CoreAssetCTEMF004Devnet1111111111111111111",
                    "owner_wallet": seller_wallet,
                    "original_buyer_wallet": seller_wallet,
                    "order_reference": "ord-seed-ct-01",
                    "tier": "General Admission",
                    "status": "issued",
                    "original_price_zar": 500,
                    "credential_version": 1,
                    "checked_in_at": None,
                    "created_at": now.isoformat(),
                },
                {
                    "id": "tkt-afro-001",
                    "event_id": event_2_id,
                    "asset_address": "CoreAssetAfro001Devnet1111111111111111111",
                    "owner_wallet": seller_wallet,
                    "original_buyer_wallet": seller_wallet,
                    "order_reference": "ord-seed-afro-01",
                    "tier": "VIP Terrace",
                    "status": "issued",
                    "original_price_zar": 1000,
                    "credential_version": 1,
                    "checked_in_at": None,
                    "created_at": now.isoformat(),
                },
                {
                    "id": "tkt-soweto-001",
                    "event_id": event_3_id,
                    "asset_address": "CoreAssetSoweto001Devnet11111111111111111",
                    "owner_wallet": buyer_wallet,
                    "original_buyer_wallet": buyer_wallet,
                    "order_reference": "ord-seed-soweto-01",
                    "tier": "Front Lawn",
                    "status": "issued",
                    "original_price_zar": 400,
                    "credential_version": 1,
                    "checked_in_at": None,
                    "created_at": now.isoformat(),
                },
            ]
        )

        campaign_id = "cmp-ct-friends-3pk"
        self.tables["resale_campaigns"].append(
            {
                "id": campaign_id,
                "slug": "ctemf-friends-x9k2",
                "event_id": event_1_id,
                "seller_wallet": seller_wallet,
                "title": "3 Friends Can't Make CTEMF — Individual Resale Tickets",
                "status": "active",
                "created_at": now.isoformat(),
            }
        )

        self.tables["resale_listings"].extend(
            [
                {
                    "id": "lst-ct-001",
                    "campaign_id": campaign_id,
                    "ticket_id": "tkt-ct-001",
                    "seller_wallet": seller_wallet,
                    "asking_price_zar": 550,
                    "status": "active",
                    "created_at": now.isoformat(),
                },
                {
                    "id": "lst-ct-002",
                    "campaign_id": campaign_id,
                    "ticket_id": "tkt-ct-002",
                    "seller_wallet": seller_wallet,
                    "asking_price_zar": 550,
                    "status": "active",
                    "created_at": now.isoformat(),
                },
                {
                    "id": "lst-ct-003",
                    "campaign_id": campaign_id,
                    "ticket_id": "tkt-ct-003",
                    "seller_wallet": seller_wallet,
                    "asking_price_zar": 550,
                    "status": "active",
                    "created_at": now.isoformat(),
                },
            ]
        )

        self.tables["ledger_accounts"].extend(
            [
                {"code": "1010", "name": "Payment Provider Clearing", "account_type": "asset"},
                {"code": "2010", "name": "Seller Resale Payable (95%)", "account_type": "liability"},
                {"code": "2020", "name": "Buyer Unsold Refund Payable (75%)", "account_type": "liability"},
                {"code": "4010", "name": "EventPass Marketplace Fee Revenue (5%)", "account_type": "revenue"},
                {"code": "4020", "name": "Refund Retention Revenue (25%)", "account_type": "revenue"},
                {"code": "5010", "name": "Ticket Liability / Refund Settlement", "account_type": "expense"},
            ]
        )


@lru_cache
def get_dev_store() -> DevSupabaseClient:
    """Singleton DevSupabaseClient shared across requests in local dev mode."""
    return DevSupabaseClient(seed=True)
