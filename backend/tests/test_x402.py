"""Tests for the x402 (HTTP 402) agent payment rail."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.main import app
from backend.routes import x402 as x402_module
from backend.tests.fake_supabase import FakeSupabaseClient


@pytest.fixture
def test_env(monkeypatch):
    fake_db = FakeSupabaseClient(
        tables={
            "tickets": [
                {
                    "id": "ticket-402",
                    "event_id": "event-1",
                    "asset_address": "Asset402",
                    "owner_wallet": "SellerWallet402",
                    "status": "listed",
                    "original_price_zar": 500,
                    "credential_version": 1,
                }
            ],
            "resale_listings": [
                {
                    "id": "listing-402",
                    "ticket_id": "ticket-402",
                    "seller_wallet": "SellerWallet402",
                    "asking_price_zar": 550,
                    "status": "active",
                }
            ],
            "transactions": [],
        }
    )

    test_settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_key="test-key",
        x402_pay_to_address="DevnetTreasuryWallet11111111111111111111111",
        x402_facilitator_url="https://x402.org/facilitator",
        zar_to_usdc_rate="0.055",
    )

    transfer_mock = MagicMock()
    monkeypatch.setattr(x402_module, "finalize_solana_transfer", transfer_mock)

    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_supabase_client] = lambda: fake_db

    yield TestClient(app), fake_db, transfer_mock

    app.dependency_overrides.clear()


def test_x402_returns_402_challenge_when_no_signature(test_env):
    client, _, transfer_mock = test_env

    resp = client.get("/api/listings/listing-402/purchase-x402")
    assert resp.status_code == 402
    assert resp.headers["Network"] == "solana-devnet"
    assert resp.headers["Asset"] == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    assert resp.headers["payTo"] == "DevnetTreasuryWallet11111111111111111111111"
    # 550 ZAR * 0.055 * 1_000_000 = 30_250_000 USDC micro-units
    assert resp.headers["Amount"] == "30250000"
    transfer_mock.assert_not_called()


def test_x402_settles_with_valid_payment_signature(test_env):
    client, fake_db, transfer_mock = test_env

    resp = client.get(
        "/api/listings/listing-402/purchase-x402",
        headers={"PAYMENT-SIGNATURE": "valid-devnet-signed-tx-payload"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "settled"
    assert body["ticket_id"] == "ticket-402"
    assert body["amount_usdc_micro"] == 30250000
    assert body["network"] == "solana-devnet"

    assert len(fake_db.tables["transactions"]) == 1
    assert fake_db.tables["transactions"][0]["provider"] == "x402"
    assert fake_db.tables["transactions"][0]["status"] == "settled"
    assert fake_db.tables["resale_listings"][0]["status"] == "sold"
    assert fake_db.tables["tickets"][0]["status"] == "sold"

    transfer_mock.assert_called_once_with(
        "ticket-402", "AgentBuyerWallet111111111111111111111111111"
    )

    # Subsequent purchase attempt on sold listing returns 409 Conflict
    replay_resp = client.get(
        "/api/listings/listing-402/purchase-x402",
        headers={"PAYMENT-SIGNATURE": "valid-devnet-signed-tx-payload"},
    )
    assert replay_resp.status_code == 409


def test_x402_rejects_invalid_signature(test_env):
    client, fake_db, transfer_mock = test_env

    resp = client.get(
        "/api/listings/listing-402/purchase-x402",
        headers={"PAYMENT-SIGNATURE": "invalid"},
    )
    assert resp.status_code == 402
    assert len(fake_db.tables["transactions"]) == 0
    assert fake_db.tables["resale_listings"][0]["status"] == "active"
    transfer_mock.assert_not_called()


def test_x402_missing_listing_returns_404(test_env):
    client, _, _ = test_env

    resp = client.get("/api/listings/nonexistent/purchase-x402")
    assert resp.status_code == 404
