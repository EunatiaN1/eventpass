"""Environment configuration loader for EventPass backend."""

from functools import lru_cache
import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

PLACEHOLDER_URLS = {"", "https://your-project-ref.supabase.co"}
PLACEHOLDER_KEYS = {"", "your-supabase-service-role-key"}


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    supabase_url: str = ""
    supabase_key: str = ""
    payfast_secret: str = ""
    paystack_secret: str = ""
    x402_pay_to_address: str = "DevnetTreasuryWallet11111111111111111111111"
    x402_facilitator_url: str = "https://x402.org/facilitator"
    zar_to_usdc_rate: str = "0.055"
    qr_signing_secret: str = "devnet-qr-credential-signing-key-change-in-prod"
    qr_key_id: str = "ep-devnet-k1"

    @property
    def use_dev_store(self) -> bool:
        """Return True when Supabase credentials are absent or placeholder values."""
        return (
            self.supabase_url.strip() in PLACEHOLDER_URLS
            or self.supabase_key.strip() in PLACEHOLDER_KEYS
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance populated from the environment."""
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_key=os.getenv("SUPABASE_KEY", ""),
        payfast_secret=os.getenv("PAYFAST_SECRET", ""),
        paystack_secret=os.getenv("PAYSTACK_SECRET", ""),
        x402_pay_to_address=os.getenv(
            "X402_PAY_TO_ADDRESS", "DevnetTreasuryWallet11111111111111111111111"
        ),
        x402_facilitator_url=os.getenv(
            "X402_FACILITATOR_URL", "https://x402.org/facilitator"
        ),
        zar_to_usdc_rate=os.getenv("ZAR_TO_USDC_RATE", "0.055"),
        qr_signing_secret=os.getenv(
            "QR_SIGNING_SECRET", "devnet-qr-credential-signing-key-change-in-prod"
        ),
        qr_key_id=os.getenv("QR_KEY_ID", "ep-devnet-k1"),
    )
