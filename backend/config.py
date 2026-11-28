"""Environment configuration loader using pydantic-settings for EventPass."""

from functools import lru_cache
from typing import List
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_URLS = {"", "https://your-project-ref.supabase.co"}
PLACEHOLDER_KEYS = {"", "your-supabase-service-role-key"}


class Settings(BaseSettings):
    """Application settings loaded securely from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    debug: bool = False
    reload: bool = False

    # Supabase (service role key stays strictly on backend)
    supabase_url: str = ""
    supabase_key: str = ""

    # JWT & Auth
    jwt_secret: str = "devnet-jwt-secret-change-in-production-min-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # Strict CORS allowlist (never ["*"])
    allowed_origin_regex: str = ""
    allowed_origins: List[str] = [
        "http://localhost:8081",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "https://eventpass.co.za",
    ]

    # Fiat payment secrets
    payfast_secret: str = ""
    payfast_merchant_id: str = ""
    payfast_merchant_key: str = ""
    payfast_passphrase: str = ""
    payfast_sandbox: bool = True
    app_public_url: str = "https://eventpass.co.za"
    paystack_secret: str = ""

    # Passwordless email OTP delivery (Resend)
    resend_api_key: str = ""
    auth_from_email: str = "EventPass <login@eventpass.co.za>"

    # x402 / Solana Devnet
    x402_pay_to_address: str = "DevnetTreasuryWallet11111111111111111111111"
    x402_facilitator_url: str = "https://x402.org/facilitator"
    zar_to_usdc_rate: str = "0.055"
    solana_private_key: str = Field(default="", validation_alias=AliasChoices("BACKEND_SOLANA_PRIVATE_KEY", "SOLANA_PRIVATE_KEY"))
    solana_rpc_url: str = "https://api.devnet.solana.com"
    eventpass_program_id: str = ""

    # QR signing
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
    """Return cached Settings instance populated from .env / environment."""
    return Settings()
