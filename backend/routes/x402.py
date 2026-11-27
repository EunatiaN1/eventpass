"""x402 (HTTP 402) agent payment rail for Solana Devnet USDC settlement."""

from decimal import Decimal, ROUND_HALF_UP
import hashlib
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response, status
from supabase import Client

from backend.config import Settings, get_settings
from backend.database import get_supabase_client
from backend.schemas.common import ListingStatus, PaymentProvider, TransactionStatus
from backend.schemas.x402 import X402SettlementResponse, X402VerificationResult
from backend.services.settlement import complete_resale_settlement
from backend.services.solana import finalize_solana_transfer

router = APIRouter(prefix="/api/listings", tags=["x402"])

SOLANA_DEVNET_NETWORK = "solana-devnet"
USDC_DEVNET_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_MICRO_UNITS = Decimal("1000000")


def zar_to_usdc_micro_units(asking_price_zar: int, zar_to_usdc_rate: str) -> int:
    """Convert integer ZAR amount to USDC micro-units (6 decimals) without float drift."""
    usdc_amount = Decimal(asking_price_zar) * Decimal(zar_to_usdc_rate) * USDC_MICRO_UNITS
    return int(usdc_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def verify_x402_payment_signature(
    payment_signature: str,
    expected_amount_micro: int,
    pay_to_address: str,
    facilitator_url: str,
) -> X402VerificationResult:
    """Mock x402 facilitator verification call for Devnet development.

    In production, this will POST to `{facilitator_url}/verify` and `/settle`
    and validate the exact network, mint, recipient, and amount.
    """
    sig = payment_signature.strip()
    if not sig or sig.lower() == "invalid":
        return X402VerificationResult(
            is_valid=False,
            payment_reference="",
            reason="Rejected by mock x402 facilitator.",
        )

    # Derive a deterministic payment_reference for idempotency/replay protection
    sig_digest = hashlib.sha256(sig.encode("utf-8")).hexdigest()[:24]
    return X402VerificationResult(
        is_valid=True,
        payment_reference=f"x402_{sig_digest}",
        buyer_wallet="AgentBuyerWallet111111111111111111111111111",
    )


@router.get(
    "/{listing_id}/purchase-x402",
    response_model=X402SettlementResponse,
    responses={402: {"description": "Payment Required - x402 payment challenge"}},
)
async def purchase_listing_x402(
    listing_id: str,
    background_tasks: BackgroundTasks,
    payment_signature: Optional[str] = Header(default=None, alias="PAYMENT-SIGNATURE"),
    settings: Settings = Depends(get_settings),
    db: Client = Depends(get_supabase_client),
):
    """Return an HTTP 402 x402 challenge or settle the listing when PAYMENT-SIGNATURE is provided."""
    listing_resp = (
        db.table("resale_listings").select("*").eq("id", listing_id).execute()
    )
    if not listing_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing not found: {listing_id}",
        )

    listing = listing_resp.data[0]
    if listing.get("status") != ListingStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Listing {listing_id} is not active (status={listing.get('status')}).",
        )

    amount_usdc_micro = zar_to_usdc_micro_units(
        int(listing["asking_price_zar"]),
        settings.zar_to_usdc_rate,
    )

    if not payment_signature:
        return Response(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            headers={
                "Network": SOLANA_DEVNET_NETWORK,
                "Asset": USDC_DEVNET_MINT,
                "payTo": settings.x402_pay_to_address,
                "Amount": str(amount_usdc_micro),
            },
        )

    verification = verify_x402_payment_signature(
        payment_signature=payment_signature,
        expected_amount_micro=amount_usdc_micro,
        pay_to_address=settings.x402_pay_to_address,
        facilitator_url=settings.x402_facilitator_url,
    )
    if not verification.is_valid:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=verification.reason or "Invalid x402 payment signature.",
        )

    # Replay protection: prevent reusing a settled payment_reference across orders
    existing_tx = (
        db.table("transactions")
        .select("id, status")
        .eq("payment_reference", verification.payment_reference)
        .execute()
    )
    if existing_tx.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment signature has already been consumed.",
        )

    ticket_id: str = listing["ticket_id"]

    db.table("transactions").insert(
        {
            "payment_reference": verification.payment_reference,
            "provider": PaymentProvider.X402.value,
            "amount": amount_usdc_micro,
            "status": TransactionStatus.SETTLED.value,
            "ticket_id": ticket_id,
            "listing_id": listing_id,
            "buyer_wallet": verification.buyer_wallet,
            "payment_method": "x402",
            "currency": "USDC",
        }
    ).execute()

    complete_resale_settlement(
        db=db,
        payment_reference=verification.payment_reference,
        ticket_id=ticket_id,
        buyer_wallet=verification.buyer_wallet,
        listing_id=listing_id,
        currency="USDC",
    )

    background_tasks.add_task(
        finalize_solana_transfer, ticket_id, verification.buyer_wallet
    )

    return X402SettlementResponse(
        status="settled",
        listing_id=listing_id,
        ticket_id=ticket_id,
        payment_reference=verification.payment_reference,
        network=SOLANA_DEVNET_NETWORK,
        asset=USDC_DEVNET_MINT,
        amount_usdc_micro=amount_usdc_micro,
        buyer_wallet=verification.buyer_wallet,
    )
