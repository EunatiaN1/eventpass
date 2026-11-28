"""EventPass Anchor program client for real Solana Devnet transactions."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from backend.config import Settings

logger = logging.getLogger(__name__)
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"


class SolanaConfigurationError(RuntimeError):
    pass


def _keypair(secret: str):
    import base58
    from solders.keypair import Keypair

    value = secret.strip()
    if value.startswith("["):
        raw = bytes(json.loads(value))
    else:
        raw = base58.b58decode(value)
    if len(raw) == 64:
        return Keypair.from_bytes(raw)
    if len(raw) == 32:
        return Keypair.from_seed(raw)
    raise SolanaConfigurationError("BACKEND_SOLANA_PRIVATE_KEY must encode a 32- or 64-byte keypair.")


def _program_id(settings: Settings):
    from solders.pubkey import Pubkey

    value = settings.eventpass_program_id.strip()
    if not value:
        raise SolanaConfigurationError("EVENTPASS_PROGRAM_ID is required before on-chain operations.")
    try:
        return Pubkey.from_string(value)
    except ValueError as exc:
        raise SolanaConfigurationError("EVENTPASS_PROGRAM_ID is not a valid Solana address.") from exc


def _string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) > 200:
        raise ValueError("Anchor string argument exceeds 200 bytes.")
    return len(encoded).to_bytes(4, "little") + encoded


async def _send_instruction(settings: Settings, instruction, authority):
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Confirmed
    from solders.message import Message
    from solders.transaction import Transaction

    async with AsyncClient(settings.solana_rpc_url, commitment=Confirmed, timeout=30) as client:
        blockhash = (await client.get_latest_blockhash(commitment=Confirmed)).value.blockhash
        message = Message.new_with_blockhash(
            [instruction],
            fee_payer=authority.pubkey(),
            blockhash=blockhash,
        )
        transaction = Transaction([authority], message, blockhash)
        signature = (await client.send_transaction(transaction)).value
        confirmation = await client.confirm_transaction(signature, commitment=Confirmed)
        if not confirmation.value or confirmation.value[0].err:
            raise RuntimeError(f"Solana transaction failed confirmation: {confirmation.value}")
        return str(signature)


def _anchor_discriminator(name: str) -> bytes:
    return hashlib.sha256(f"global:{name}".encode()).digest()[:8]


async def initialize_event(event_id: str, organizer_wallet: str, settings: Settings) -> tuple[str, str]:
    from solders.instruction import AccountMeta, Instruction
    from solders.pubkey import Pubkey

    program_id = _program_id(settings)
    authority = _keypair(settings.solana_private_key)
    organizer = Pubkey.from_string(organizer_wallet)
    event_pda, _ = Pubkey.find_program_address([b"event", event_id.encode()], program_id)
    system_program = Pubkey.from_string(SYSTEM_PROGRAM_ID)
    data = _anchor_discriminator("initialize_event") + _string(event_id) + bytes(organizer)
    instruction = Instruction(
        program_id,
        [
            AccountMeta(authority.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(event_pda, is_signer=False, is_writable=True),
            AccountMeta(system_program, is_signer=False, is_writable=False),
        ],
        data,
    )
    signature = await _send_instruction(settings, instruction, authority)
    logger.info("eventpass initialize_event confirmed event_id=%s signature=%s", event_id, signature)
    return str(event_pda), signature


async def mint_ticket(
    *,
    event_id: str,
    ticket_id: str,
    name: str,
    uri: str,
    owner_wallet: str,
    settings: Settings,
) -> tuple[str, str | None]:
    """Mint a Core asset using the deployed EventPass Anchor program.

    Returns the deterministic asset PDA and transaction signature. If the
    on-chain ticket record already exists and matches, returns None signature.
    """
    from solana.rpc.async_api import AsyncClient
    from solders.instruction import AccountMeta, Instruction
    from solders.pubkey import Pubkey

    program_id = _program_id(settings)
    authority = _keypair(settings.solana_private_key)
    organizer = Pubkey.from_string(owner_wallet)
    event_pda, _ = Pubkey.find_program_address([b"event", event_id.encode()], program_id)
    record_pda, _ = Pubkey.find_program_address([b"ticket", ticket_id.encode()], program_id)
    asset_pda, _ = Pubkey.find_program_address([b"asset", ticket_id.encode()], program_id)
    core_program = Pubkey.from_string("CoREENxT6tW1HoK8ypY1SxRMZTcVPm7R94rH4PZNhX7d")
    system_program = Pubkey.from_string(SYSTEM_PROGRAM_ID)

    async with AsyncClient(settings.solana_rpc_url, commitment="confirmed", timeout=30) as client:
        existing = await client.get_account_info(record_pda)
        account = existing.value
        if account is not None:
            data = bytes(account.data)
            if account.owner != program_id or len(data) < 104:
                raise RuntimeError("Existing on-chain ticket record is invalid.")
            if data[8:40] != bytes(event_pda) or data[40:72] != bytes(asset_pda) or data[72:104] != bytes(organizer):
                raise RuntimeError("Existing on-chain ticket record does not match this order.")
            return str(asset_pda), None

        data = (
            _anchor_discriminator("mint_ticket")
            + _string(event_id)
            + _string(ticket_id)
            + _string(name)
            + _string(uri)
        )
        instruction = Instruction(
            program_id,
            [
                AccountMeta(authority.pubkey(), is_signer=True, is_writable=True),
                AccountMeta(event_pda, is_signer=False, is_writable=False),
                AccountMeta(record_pda, is_signer=False, is_writable=True),
                AccountMeta(asset_pda, is_signer=False, is_writable=True),
                AccountMeta(organizer, is_signer=False, is_writable=False),
                AccountMeta(core_program, is_signer=False, is_writable=False),
                AccountMeta(system_program, is_signer=False, is_writable=False),
            ],
            data,
        )
        from solana.rpc.commitment import Confirmed
        from solders.message import Message
        from solders.transaction import Transaction

        blockhash = (await client.get_latest_blockhash(commitment=Confirmed)).value.blockhash
        message = Message.new_with_blockhash([instruction], authority.pubkey(), blockhash)
        transaction = Transaction([authority], message, blockhash)
        signature = (await client.send_transaction(transaction)).value
        confirmation = await client.confirm_transaction(signature, commitment=Confirmed)
        if not confirmation.value or confirmation.value[0].err:
            raise RuntimeError(f"Solana mint failed confirmation: {confirmation.value}")
        logger.info("eventpass mint_ticket confirmed ticket_id=%s asset=%s signature=%s", ticket_id, asset_pda, signature)
        return str(asset_pda), str(signature)


async def check_in_ticket(
    *, event_id: str, ticket_id: str, settings: Settings
) -> str:
    from solana.rpc.async_api import AsyncClient
    from solders.instruction import AccountMeta, Instruction
    from solders.pubkey import Pubkey
    from solders.message import Message
    from solders.transaction import Transaction

    program_id = _program_id(settings)
    scanner = _keypair(settings.solana_private_key)
    event_pda, _ = Pubkey.find_program_address([b"event", event_id.encode()], program_id)
    record_pda, _ = Pubkey.find_program_address([b"ticket", ticket_id.encode()], program_id)
    account_info = await _asset_from_record(settings, record_pda)
    asset = Pubkey.from_string(account_info)
    data = _anchor_discriminator("check_in") + _string(event_id) + _string(ticket_id)
    async with AsyncClient(settings.solana_rpc_url, timeout=30) as client:
        existing = (await client.get_account_info(record_pda)).value
    if existing is None or existing.owner != program_id:
        raise RuntimeError("On-chain ticket record was not found.")
    account_data = bytes(existing.data)
    checked_index = 108 + len(ticket_id.encode("utf-8"))
    if len(account_data) > checked_index and account_data[checked_index] == 1:
        return "already_checked_in"

    instruction = Instruction(program_id, [
        AccountMeta(scanner.pubkey(), is_signer=True, is_writable=False),
        AccountMeta(event_pda, is_signer=False, is_writable=False),
        AccountMeta(record_pda, is_signer=False, is_writable=True),
        AccountMeta(asset, is_signer=False, is_writable=False),
    ], data)
    return await _send_instruction(settings, instruction, scanner)


async def _asset_from_record(settings: Settings, record_pda) -> str:
    from solana.rpc.async_api import AsyncClient
    from solders.pubkey import Pubkey

    program_id = _program_id(settings)
    async with AsyncClient(settings.solana_rpc_url, commitment="confirmed", timeout=30) as client:
        account = (await client.get_account_info(record_pda)).value
    if account is None or account.owner != program_id or len(bytes(account.data)) < 72:
        raise RuntimeError("On-chain ticket record was not found.")
    return str(Pubkey.from_bytes(bytes(account.data)[40:72]))


# Backwards-compatible name retained for the resale settlement route. Direct
# transfers are intentionally rejected until assets are minted with a transfer
# delegate and the resale instruction is deployed.
def finalize_solana_transfer(ticket_id: str, buyer_wallet: str | None, db: Any = None) -> None:
    raise RuntimeError(
        "On-chain resale transfers are unavailable until transfer delegation is configured."
    )
