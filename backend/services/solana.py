"""Real Solana Devnet transfer for Metaplex Core assets using solana-py + solders.

Architecture decision:
  Metaplex Core uses a custom program (mpl-core) with its own instruction set.
  We build the transfer instruction manually against the program's on-chain ABI
  since there is no official Python SDK for mpl-core. The instruction layout
  matches the Metaplex Core IDL v1 transfer discriminator.

  Discriminator for `transfer`: [163, 52, 200, 231, 140, 3, 69, 186]  (anchor hash)

  If the private key is absent or Devnet is unreachable, the function falls back
  to logging and marks the job as `needs_reconciliation` for the CRON to retry.
"""

from __future__ import annotations

import asyncio
import base58
import logging
import struct
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metaplex Core program ID on all clusters
# ---------------------------------------------------------------------------
MPL_CORE_PROGRAM_ID = "CoREENxT6tW1HoK8ypY1SxRMZTcVPm7R94rH4PZNhX7d"

# Transfer instruction discriminator (Anchor sha256("global:transfer")[:8])
TRANSFER_DISCRIMINATOR = bytes([163, 52, 200, 231, 140, 3, 69, 186])


def _load_keypair(b58_private_key: str):
    """Decode a base-58 64-byte secret key into a solders Keypair."""
    from solders.keypair import Keypair  # type: ignore

    raw = base58.b58decode(b58_private_key)
    if len(raw) == 64:
        return Keypair.from_bytes(raw)
    if len(raw) == 32:
        return Keypair.from_seed(raw)
    raise ValueError(f"Unexpected key length {len(raw)}: must be 32 or 64 bytes.")


def _build_transfer_ix(
    asset_pubkey,
    authority_pubkey,
    new_owner_pubkey,
    payer_pubkey,
):
    """
    Build a Metaplex Core 'transfer' instruction.

    Accounts (positional, matching mpl-core IDL):
      0  asset         – the Core NFT account (writable)
      1  collection    – optional collection (can be omitted / program_id as placeholder)
      2  payer         – pays for any reallocs (writable, signer)
      3  authority     – current owner / update authority (signer)
      4  newOwner      – recipient (writable)
      5  systemProgram – 11111…
      6  logWrapper    – noop (spl-noop) or system program
    """
    from solders.instruction import AccountMeta, Instruction  # type: ignore
    from solders.pubkey import Pubkey  # type: ignore

    SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
    SPL_NOOP = Pubkey.from_string("noopb9bkMVfRPU8AsbpTUg8AQkHtKwMYZiFUjNRtMmV")

    # compressionProof argument: None → serialize as option byte 0x00
    data = TRANSFER_DISCRIMINATOR + b"\x00"

    accounts = [
        AccountMeta(pubkey=asset_pubkey, is_signer=False, is_writable=True),
        # collection (None in our case – pass system program as placeholder)
        AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(pubkey=payer_pubkey, is_signer=True, is_writable=True),
        AccountMeta(pubkey=authority_pubkey, is_signer=True, is_writable=False),
        AccountMeta(pubkey=new_owner_pubkey, is_signer=False, is_writable=False),
        AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
        AccountMeta(pubkey=SPL_NOOP, is_signer=False, is_writable=False),
    ]

    return Instruction(
        program_id=Pubkey.from_string(MPL_CORE_PROGRAM_ID),
        accounts=accounts,
        data=bytes(data),
    )


async def _execute_transfer(
    asset_address: str,
    to_wallet: str,
    private_key_b58: str,
    rpc_url: str = "https://api.devnet.solana.com",
) -> str:
    """
    Build, sign, and send the mpl-core transfer transaction.
    Returns the transaction signature string on success.
    Raises on failure.
    """
    from solana.rpc.async_api import AsyncClient  # type: ignore
    from solana.rpc.commitment import Confirmed  # type: ignore
    from solders.pubkey import Pubkey  # type: ignore
    from solders.transaction import Transaction  # type: ignore
    from solders.message import Message  # type: ignore

    authority_kp = _load_keypair(private_key_b58)
    authority_pk = authority_kp.pubkey()
    asset_pk = Pubkey.from_string(asset_address)
    new_owner_pk = Pubkey.from_string(to_wallet)

    ix = _build_transfer_ix(
        asset_pubkey=asset_pk,
        authority_pubkey=authority_pk,
        new_owner_pubkey=new_owner_pk,
        payer_pubkey=authority_pk,
    )

    async with AsyncClient(rpc_url) as client:
        # Fetch a fresh blockhash
        blockhash_resp = await client.get_latest_blockhash(commitment=Confirmed)
        recent_blockhash = blockhash_resp.value.blockhash

        msg = Message.new_with_blockhash(
            [ix],
            fee_payer=authority_pk,
            blockhash=recent_blockhash,
        )
        tx = Transaction([authority_kp], msg, recent_blockhash)

        result = await client.send_transaction(
            tx,
            opts={"skip_preflight": False, "preflight_commitment": "confirmed"},
        )
        sig = str(result.value)

        # Wait for confirmation (up to ~30 s)
        await client.confirm_transaction(sig, commitment=Confirmed)

    return sig


def finalize_solana_transfer(
    ticket_id: str,
    buyer_wallet: Optional[str],
    db: Any = None,
) -> None:
    """
    Real Metaplex Core transfer dispatched as a FastAPI BackgroundTask.

    1. Loads backend hot-wallet from settings.
    2. Builds & sends the on-chain mpl-core transfer instruction.
    3. On success → marks outbox_job 'completed', updates ticket status to 'transferred'.
    4. On failure → marks outbox_job 'needs_reconciliation' (CRON will retry up to 3×).
    """
    # Import lazily to avoid circular imports at module load time
    from backend.config import get_settings

    settings = get_settings()
    private_key = settings.solana_private_key.strip()

    # -----------------------------------------------------------------------
    # Resolve the asset_address from the DB
    # -----------------------------------------------------------------------
    asset_address: Optional[str] = None
    if db is not None:
        try:
            t_resp = db.table("tickets").select("asset_address").eq("id", ticket_id).execute()
            if t_resp.data:
                asset_address = t_resp.data[0].get("asset_address")
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Guard: missing key or placeholder wallet → log and mark reconciliation
    # -----------------------------------------------------------------------
    if not private_key or not buyer_wallet or not asset_address:
        reason = (
            "no private key configured"
            if not private_key
            else "missing buyer_wallet or asset_address"
        )
        logger.warning(
            "Solana transfer skipped (ticket_id=%s): %s – marking needs_reconciliation",
            ticket_id,
            reason,
        )
        _mark_outbox(db, ticket_id, "needs_reconciliation", error=reason)
        return

    # -----------------------------------------------------------------------
    # Execute the real on-chain transfer
    # -----------------------------------------------------------------------
    try:
        sig = asyncio.run(
            _execute_transfer(
                asset_address=asset_address,
                to_wallet=buyer_wallet,
                private_key_b58=private_key,
                rpc_url="https://api.devnet.solana.com",
            )
        )
        logger.info(
            "✅ Solana transfer confirmed ticket_id=%s → %s  sig=%s",
            ticket_id,
            buyer_wallet,
            sig,
        )
        _mark_outbox(db, ticket_id, "completed", tx_signature=sig)
        # Advance ticket to 'transferred'
        if db is not None:
            db.table("tickets").update(
                {"status": "transferred", "updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", ticket_id).execute()

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "❌ Solana transfer failed ticket_id=%s: %s – marking needs_reconciliation",
            ticket_id,
            exc,
        )
        _mark_outbox(db, ticket_id, "needs_reconciliation", error=str(exc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mark_outbox(
    db: Any,
    ticket_id: str,
    status: str,
    tx_signature: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Update the outbox_jobs row for this ticket's solana_devnet_transfer job."""
    if db is None:
        return
    try:
        payload: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if tx_signature:
            payload["tx_signature"] = tx_signature
        if error:
            payload["last_error"] = error[:500]

        db.table("outbox_jobs").update(payload).eq("job_type", "solana_devnet_transfer").eq(
            "payload->>ticket_id", ticket_id
        ).execute()
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not update outbox_jobs for ticket_id=%s: %s", ticket_id, e)
