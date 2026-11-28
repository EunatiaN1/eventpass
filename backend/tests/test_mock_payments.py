"""Tests for the test-only primary checkout confirmation endpoint."""

from fastapi.testclient import TestClient
import pytest

from backend.auth import create_access_token
from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.main import app
from backend.tests.fake_supabase import FakeSupabaseClient


@pytest.fixture
def mock_checkout():
    buyer = "BuyerWalletCheckout111111111111111111111111"
    db = FakeSupabaseClient(
        tables={
            "profiles": [],
            "tickets": [
                {
                    "id": "ticket-checkout-1",
                    "order_reference": "ord-checkout-123",
                    "owner_wallet": buyer,
                    "status": "reserved",
                },
                {
                    "id": "ticket-checkout-2",
                    "order_reference": "ord-checkout-123",
                    "owner_wallet": buyer,
                    "status": "reserved",
                },
            ],
            "transactions": [
                {
                    "id": "tx-checkout-123",
                    "payment_reference": "ord-checkout-123",
                    "payment_method": "eft",
                    "buyer_wallet": buyer,
                    "ticket_id": "ticket-checkout-1",
                    "amount": 1000,
                    "status": "pending",
                }
            ],
        }
    )
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_key="test-key",
        x402_pay_to_address="PublicDevnetTreasury111",
        zar_to_usdc_rate="0.055",
    )
    token = create_access_token("buyer-1", buyer, "buyer", settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_supabase_client] = lambda: db
    yield TestClient(app), db, {"Authorization": f"Bearer {token}"}, buyer
    app.dependency_overrides.clear()


def test_mock_success_atomically_settles_order_and_is_idempotent(mock_checkout):
    client, db, headers, _buyer = mock_checkout
    body = {"ticket_id": "ticket-checkout-1", "payment_method": "eft"}

    first = client.post("/api/webhooks/mock-success", json=body, headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "settled"
    assert first.json()["idempotent"] is False
    assert first.json()["simulation"] is True
    assert db.tables["transactions"][0]["status"] == "settled"
    assert [ticket["status"] for ticket in db.tables["tickets"]] == ["sold", "sold"]

    second = client.post("/api/webhooks/mock-success", json=body, headers=headers)
    assert second.status_code == 200
    assert second.json()["status"] == "already_settled"
    assert second.json()["idempotent"] is True


def test_mock_success_rejects_wrong_method_without_mutation(mock_checkout):
    client, db, headers, _buyer = mock_checkout
    response = client.post(
        "/api/webhooks/mock-success",
        json={"ticket_id": "ticket-checkout-1", "payment_method": "card"},
        headers=headers,
    )
    assert response.status_code == 409
    assert db.tables["transactions"][0]["status"] == "pending"
    assert [ticket["status"] for ticket in db.tables["tickets"]] == ["reserved", "reserved"]


def test_checkout_config_exposes_only_public_pay_to_address(mock_checkout):
    client, _db, _headers, _buyer = mock_checkout
    response = client.get("/api/checkout/config?amount_zar=500")
    assert response.status_code == 200
    assert response.json()["x402_pay_to_address"] == "PublicDevnetTreasury111"
    assert response.json()["amount_usdc"] == "27.50"
    assert "private" not in response.text.lower()
