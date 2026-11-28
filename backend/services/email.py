"""Transactional email delivery for passwordless sign-in codes."""

import logging

import httpx

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when the configured email provider rejects a delivery request."""


async def send_login_code(
    *,
    email: str,
    code: str,
    api_key: str,
    from_email: str,
) -> None:
    """Send a short-lived OTP through Resend without logging the code."""
    payload = {
        "from": from_email,
        "to": [email],
        "subject": "Your EventPass sign-in code",
        "text": (
            f"Your EventPass sign-in code is {code}. It expires in 10 minutes. "
            "If you did not request this code, you can ignore this email."
        ),
        "html": (
            "<div style=\"font-family:-apple-system,BlinkMacSystemFont,Arial,sans-serif;"
            "background:#0a0a0a;color:#fff;padding:32px;border-radius:20px\">"
            "<p style=\"color:#ff8a35;text-transform:uppercase;letter-spacing:2px\">EventPass</p>"
            "<h1 style=\"font-size:24px\">Your sign-in code</h1>"
            f"<p style=\"font-size:32px;letter-spacing:8px;font-weight:700\">{code}</p>"
            "<p>This code expires in 10 minutes. If you did not request it, ignore this email.</p>"
            "</div>"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        logger.exception("Resend request failed while sending sign-in OTP")
        raise EmailDeliveryError(f"Unable to reach Resend: {exc}") from exc

    if response.is_error:
        detail = response.text[:500]
        logger.error("Resend rejected OTP request status=%s response=%s", response.status_code, detail)
        raise EmailDeliveryError(f"Resend rejected the email (HTTP {response.status_code}): {detail}")
