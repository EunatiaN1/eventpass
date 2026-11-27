"""Signed, versioned QR admission credential issuance and verification."""

import base64
import hashlib
import hmac
import json
from typing import Any, Dict, Tuple

from backend.config import Settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)


def issue_qr_credential(
    ticket: Dict[str, Any], settings: Settings
) -> str:
    """Generate a compact HMAC-SHA256 signed QR credential bound to ticket + credential_version."""
    claims = {
        "kid": settings.qr_key_id,
        "tid": ticket["id"],
        "eid": ticket["event_id"],
        "ver": int(ticket.get("credential_version", 1)),
        "asset": ticket["asset_address"],
    }
    payload_b64 = _b64url_encode(
        json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    sig = hmac.new(
        settings.qr_signing_secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"epv1.{payload_b64}.{_b64url_encode(sig)}"


def verify_qr_credential(
    token: str, settings: Settings
) -> Tuple[bool, Dict[str, Any], str]:
    """Verify QR token signature and decode claims. Returns (ok, claims, error_reason)."""
    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != "epv1":
        return False, {}, "Malformed QR credential format."

    _, payload_b64, sig_b64 = parts
    expected_sig = hmac.new(
        settings.qr_signing_secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()

    try:
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return False, {}, "Invalid QR credential signature."
        claims = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        return True, claims, ""
    except Exception:
        return False, {}, "Corrupted QR credential payload."
