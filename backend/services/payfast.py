"""PayFast Hosted Checkout and ITN verification helpers.

PayFast ITN signatures use the provider's MD5 parameter-string scheme (not HMAC).
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Iterable
from urllib.parse import quote_plus


def encode_payfast_fields(fields: Iterable[tuple[str, str]]) -> str:
    """Encode fields in their original order using PayFast-compatible form encoding."""
    return "&".join(
        f"{quote_plus(str(key), safe='~')}={quote_plus(str(value), safe='~')}"
        for key, value in fields
        if str(value) != ""
    )


def payfast_signature(fields: Iterable[tuple[str, str]], passphrase: str = "") -> str:
    """Return the MD5 signature for ordered PayFast fields and optional passphrase."""
    values = [(key, value) for key, value in fields if key.lower() != "signature"]
    parameter_string = encode_payfast_fields(values)
    if passphrase:
        parameter_string += f"&passphrase={quote_plus(passphrase, safe='~')}"
    return hashlib.md5(parameter_string.encode("utf-8")).hexdigest()


def verify_payfast_signature(fields: list[tuple[str, str]], passphrase: str) -> bool:
    """Constant-time compare the signature from an ordered PayFast form payload."""
    signatures = [value for key, value in fields if key.lower() == "signature"]
    if len(signatures) != 1 or not signatures[0]:
        return False
    return hmac.compare_digest(
        payfast_signature(fields, passphrase).lower(),
        signatures[0].strip().lower(),
    )
