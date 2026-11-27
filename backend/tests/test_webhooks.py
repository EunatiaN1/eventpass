"""Tests for PayFast and Paystack webhook endpoints."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.main import app
from backend.routes import webhooks as webhooks_module
from backend.tests.fake_supabase import FakeSupabaseClient

PAYFAST_SECRET = "test_payfast_secret"
PAYSTACK_SECRET = "test_paystack_secret"


def _sign_hmac(body: bytes, secret: str, digestmod) -> str:
    return hmac.new(secret.encode("utf-8"), body, digestmod).hexdigest()


@pytest.fixture
def test_env(monkeypatch):
    fake_db = FakeSupabaseClient(
        tables={
            "tickets": [
                {
                    "id": "ticket-1",
                    "event_id": "event-1",
                    "asset_address": "Asset111",
                    "owner_wallet": "SellerWallet111",
                    "status": "reserved",
                    "original_price_zar": 550,
                    "credential_version": 1,
                }
            ],
            "transactions": [
                {
                    "id": "tx-1",
                    "payment_reference": "ref_pf_001",
                    "provider": "payfast",
                    "amount": 550,
                    "status": "pending",
                    "ticket_id": "ticket-1",
                    "buyer_wallet": "BuyerWallet111",
                },
                {
                    "id": "tx-2",
                    "payment_reference": "ref_ps_001",
                    "provider": "paystack",
                    "amount": 55000,
                    "status": "pending",
                    "ticket_id": "ticket-1",
                    "buyer_wallet": "BuyerWallet222",
                },
            ],
        }
    )

    test_settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_key="test-key",
        payfast_secret=PAYFAST_SECRET,
        paystack_secret=PAYSTACK_SECRET,
        x402_pay_to_address="DevnetPayTo111",
    )

    transfer_mock = MagicMock()
    monkeypatch.setattr(webhooks_module, "finalize_solana_transfer", transfer_mock)

    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_supabase_client] = lambda: fake_db

    yield TestClient(app), fake_db, transfer_mock

    app.dependency_overrides.clear()


def test_payfast_webhook_success_and_idempotency(test_env):
    client, fake_db, transfer_mock = test_env
    payload = {
        "m_payment_id": "ref_pf_001",
        "pf_payment_id": "pf_999",
        "payment_status": "COMPLETE",
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = _sign_hmac(raw_body, PAYFAST_SECRET, hashlib.sha256)

    resp = client.post(
        "/api/webhooks/payfast",
        content=raw_body,
        headers={"X-PayFast-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "settled"
    assert data["idempotent"] is False
    assert fake_db.tables["transactions"][0]["status"] == "settled"
    assert fake_db.tables["tickets"][0]["status"] == "sold"
    transfer_mock.assert_called_once_with("ticket-1", "BuyerWallet111")

    # Duplicate delivery must be idempotent and not re-trigger Solana transfer
    dup_resp = client.post(
        "/api/webhooks/payfast",
        content=raw_body,
        headers={"X-PayFast-Signature": sig, "Content-Type": "application/json"},
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["status"] == "already_settled"
    assert dup_resp.json()["idempotent"] is True
    assert transfer_mock.call_count == 1


def test_payfast_webhook_invalid_signature_rejected(test_env):
    client, _, transfer_mock = test_env
    raw_body = json.dumps({"m_payment_id": "ref_pf_001", "payment_status": "COMPLETE"}).encode()

    resp = client.post(
        "/api/webhooks/payfast",
        content=raw_body,
        headers={"X-PayFast-Signature": "bad_sig", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401
    transfer_mock.assert_not_called()


def test_payfast_webhook_failed_payment(test_env):
    client, fake_db, transfer_mock = test_env
    raw_body = json.dumps({"m_payment_id": "ref_pf_001", "payment_status": "FAILED"}).encode()
    sig = _sign_hmac(raw_body, PAYFAST_SECRET, hashlib.sha256)

    resp = client.post(
        "/api/webhooks/payfast",
        content=raw_body,
        headers={"X-PayFast-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
    assert fake_db.tables["transactions"][0]["status"] == "failed"
    assert fake_db.tables["tickets"][0]["status"] == "reserved"
    transfer_mock.assert_not_called()


def test_paystack_webhook_success_and_idempotency(test_env):
    client, fake_db, transfer_mock = test_env
    payload = {
        "event": "charge.success",
        "data": {"reference": "ref_ps_001", "status": "success", "amount": 55000},
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = _sign_hmac(raw_body, PAYSTACK_SECRET, hashlib.sha512)

    resp = client.post(
        "/api/webhooks/paystack",
        content=raw_body,
        headers={"x-paystack-signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "settled"
    assert fake_db.tables["transactions"][1]["status"] == "settled"
    assert fake_db.tables["tickets"][0]["status"] == "sold"
    transfer_mock.assert_called_once_with("ticket-1", "BuyerWallet222")

    dup_resp = client.post(
        "/api/webhooks/paystack",
        content=raw_body,
        headers={"x-paystack-signature": sig, "Content-Type": "application/json"},
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["idempotent"] is True
    assert transfer_mock.call_count == 1


def test_paystack_webhook_invalid_signature_rejected(test_env):
    client, _, transfer_mock = test_env
    raw_body = json.dumps(
        {"event": "charge.success", "data": {"reference": "ref_ps_001", "status": "success"}}
    ).encode()

    resp = client.post(
        "/api/webhooks/paystack",
        content=raw_body,
        headers={"x-paystack-signature": "invalid", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401
    transfer_mock.assert_not_called()


def test_webhook_unknown_reference_returns_404(test_env):
    client, _, _ = test_env
    raw_body = json.dumps({"m_payment_id": "unknown_ref", "payment_status": "COMPLETE"}).encode()
    sig = _sign_hmac(raw_body, PAYFAST_SECRET, hashlib.sha256)

    resp = client.post(
        "/api/webhooks/payfast",
        content=raw_body,
        headers={"X-PayFast-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 404
