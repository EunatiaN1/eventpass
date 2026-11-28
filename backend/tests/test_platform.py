"""End-to-end platform tests for EventPass (campaigns, caps, 75% refunds, ledger, QR check-in)."""

from fastapi.testclient import TestClient
import pytest

from backend.auth import create_access_token
from backend.config import get_settings
from backend.database import get_supabase_client
from backend.dev_store import DevSupabaseClient
from backend.main import app

# ---------------------------------------------------------------------------
# Shared seeded wallet addresses (must match dev_store.py seeds)
# ---------------------------------------------------------------------------
SELLER_WALLET = "SellerWalletDemo11111111111111111111111111"
BUYER_WALLET = "BuyerWalletDemo222222222222222222222222222"
ORGANIZER_WALLET = "OrgWalletCapeTown111111111111111111111111"


def _make_token(wallet: str, role: str = "buyer", user_id: str | None = None) -> str:
    """Generate a valid signed JWT for a given wallet/role."""
    settings = get_settings()
    uid = user_id or f"usr-{wallet[:8].lower()}"
    return create_access_token(user_id=uid, wallet=wallet, role=role, settings=settings)


def _auth(wallet: str, role: str = "buyer", user_id: str | None = None) -> dict:
    """Return Authorization header dict for the given wallet."""
    return {"Authorization": f"Bearer {_make_token(wallet, role, user_id)}"}


def _buyer_auth() -> dict:
    return _auth(BUYER_WALLET, role="buyer", user_id="usr-buyer-demo")


def _seller_auth() -> dict:
    return _auth(SELLER_WALLET, role="buyer", user_id="usr-seller-demo")


def _organizer_auth() -> dict:
    return _auth(ORGANIZER_WALLET, role="organizer", user_id="usr-org-ct")


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    dev_db = DevSupabaseClient(seed=True)
    app.dependency_overrides[get_supabase_client] = lambda: dev_db
    yield TestClient(app), dev_db
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_web_app_and_campaign_routes_serve_html(client):
    tc, _ = client
    assert tc.get("/").status_code == 200
    assert "EventPass" in tc.get("/").text
    assert tc.get("/c/ctemf-friends-x9k2").status_code == 200


def test_multi_ticket_primary_purchase_and_campaign_price_cap(client):
    tc, _ = client
    buyer = "NewBuyerWallet1111111111111111111111111111"

    # Buy 3 tickets in one checkout -> 3 individually identifiable records
    purchase = tc.post(
        "/api/events/evt-ct-electronic-2026/purchase-primary",
        json={"buyer_wallet": buyer, "quantity": 3, "tier": "General Admission"},
        headers=_auth(buyer, role="buyer", user_id="usr-NewBuyer"),
    )
    assert purchase.status_code == 201
    tickets = purchase.json()["tickets"]
    assert len(tickets) == 3
    assert len({t["id"] for t in tickets}) == 3
    assert len({t["asset_address"] for t in tickets}) == 3

    # Confirm the test checkout through the idempotent simulation endpoint.
    settled = tc.post(
        "/api/webhooks/mock-success",
        json={"ticket_id": tickets[0]["id"], "payment_method": "card"},
        headers=_auth(buyer, role="buyer", user_id="usr-NewBuyer"),
    )
    assert settled.status_code == 200
    assert settled.json()["status"] == "settled"
    assert len(settled.json()["ticket_ids"]) == 3

    # Attempting to list above organizer cap (R600) is rejected with 422
    bad_cmp = tc.post(
        "/api/campaigns",
        json={
            "seller_wallet": buyer,
            "title": "Overpriced test",
            "items": [{"ticket_id": tickets[0]["id"], "asking_price_zar": 750}],
        },
    )
    assert bad_cmp.status_code == 422

    # Listing 2 of 3 tickets within cap creates one shareable campaign without exposing QR tokens
    good_cmp = tc.post(
        "/api/campaigns",
        json={
            "seller_wallet": buyer,
            "title": "Two spare tickets",
            "items": [
                {"ticket_id": tickets[0]["id"], "asking_price_zar": 550},
                {"ticket_id": tickets[1]["id"], "asking_price_zar": 550},
            ],
        },
    )
    assert good_cmp.status_code == 201
    slug = good_cmp.json()["slug"]

    public_view = tc.get(f"/api/campaigns/{slug}")
    assert public_view.status_code == 200
    body = public_view.json()
    assert body["available_count"] == 2
    assert "qr_token" not in public_view.text


def test_concurrent_reservation_and_partial_campaign_sale_with_qr_revocation(client):
    tc, _ = client

    # Grab seller's v1 QR token for tkt-ct-001 BEFORE resale (seller owns it)
    old_cred = tc.get(
        "/api/tickets/tkt-ct-001/credential",
        headers=_seller_auth(),
    ).json()
    old_qr_token = old_cred["qr_token"]

    # Buyer 1 initiates checkout (reserves lst-ct-001)
    buyer1 = "ResaleBuyerOne111111111111111111111111111"
    buyer2 = "ResaleBuyerTwo222222222222222222222222222"

    c1 = tc.post(
        "/api/checkout/initiate",
        json={"listing_id": "lst-ct-001", "buyer_wallet": buyer1, "payment_method": "eft"},
    )
    assert c1.status_code == 200
    assert c1.json()["pricing"]["marketplace_fee_zar_5pct"] == 27
    assert c1.json()["pricing"]["seller_proceeds_zar_95pct"] == 523
    pay_ref = c1.json()["payment_reference"]

    # Buyer 2 trying to reserve the same listing gets 409 Conflict
    c2 = tc.post(
        "/api/checkout/initiate",
        json={"listing_id": "lst-ct-001", "buyer_wallet": buyer2, "payment_method": "card"},
    )
    assert c2.status_code == 409

    # Confirm verified settlement for Buyer 1
    settle = tc.post(
        "/api/checkout/confirm-demo",
        json={"payment_reference": pay_ref, "simulate_outcome": "success"},
    )
    assert settle.status_code == 200
    assert settle.json()["status"] == "settled"

    # Multi-ticket campaign remains active with 2 of 3 tickets still available
    cmp_view = tc.get("/api/campaigns/ctemf-friends-x9k2").json()
    assert cmp_view["campaign"]["status"] == "active"
    assert cmp_view["available_count"] == 2

    # Ledger has a balanced double-entry journal for this resale
    ledger = tc.get("/api/ledger", headers=_organizer_auth()).json()
    assert len(ledger["journals"]) == 1
    debits = sum(e["amount"] for e in ledger["entries"] if e["direction"] == "debit")
    credits = sum(e["amount"] for e in ledger["entries"] if e["direction"] == "credit")
    assert debits == credits == 550

    # Seller's old v1 QR is now revoked at the gate
    old_scan = tc.post(
        "/api/check-in",
        json={"event_id": "evt-ct-electronic-2026", "qr_token": old_qr_token},
        headers=_organizer_auth(),
    ).json()
    assert old_scan["accepted"] is False
    assert old_scan["result"] == "credential_revoked"

    # Buyer's new v2 QR succeeds once, and duplicate scan is rejected
    # ticket is now owned by buyer1; use buyer1 token
    new_cred = tc.get(
        "/api/tickets/tkt-ct-001/credential",
        headers=_auth(buyer1, role="buyer", user_id="usr-buyer1"),
    ).json()
    assert new_cred["credential_version"] == 2
    assert new_cred["owner_wallet"] == buyer1

    first_scan = tc.post(
        "/api/check-in",
        json={"event_id": "evt-ct-electronic-2026", "qr_token": new_cred["qr_token"]},
        headers=_organizer_auth(),
    ).json()
    assert first_scan["accepted"] is True

    dup_scan = tc.post(
        "/api/check-in",
        json={"event_id": "evt-ct-electronic-2026", "qr_token": new_cred["qr_token"]},
        headers=_organizer_auth(),
    ).json()
    assert dup_scan["accepted"] is False
    assert dup_scan["result"] == "already_checked_in"


def test_unsold_75_percent_refund_and_15_day_cutoff(client):
    tc, _ = client

    # tkt-afro-001 is R1,000 and event is 28 days away -> eligible for R750 refund
    # seller owns tkt-afro-001
    cred_before = tc.get(
        "/api/tickets/tkt-afro-001/credential",
        headers=_seller_auth(),
    ).json()

    refund_resp = tc.post(
        "/api/tickets/tkt-afro-001/refund",
        json={"requester_wallet": SELLER_WALLET},
        headers=_seller_auth(),
    )
    assert refund_resp.status_code == 200
    body = refund_resp.json()
    assert body["original_price_zar"] == 1000
    assert body["refund_amount_zar"] == 750
    assert body["retained_amount_zar"] == 250

    # Credential endpoint rejects refunded ticket & gate scanner blocks old QR
    assert tc.get(
        "/api/tickets/tkt-afro-001/credential",
        headers=_seller_auth(),
    ).status_code == 409

    scan = tc.post(
        "/api/check-in",
        json={"event_id": "evt-afrofuture-jhb-2026", "qr_token": cred_before["qr_token"]},
        headers=_organizer_auth(),
    ).json()
    assert scan["accepted"] is False
    assert scan["result"] == "refunded"

    # tkt-soweto-001 is 10 days before event (past 15-day cutoff) -> rejected with 409
    late_refund = tc.post(
        "/api/tickets/tkt-soweto-001/refund",
        json={"requester_wallet": BUYER_WALLET},
        headers=_buyer_auth(),
    )
    assert late_refund.status_code == 409
