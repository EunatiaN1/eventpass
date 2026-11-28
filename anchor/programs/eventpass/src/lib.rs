use anchor_lang::prelude::*;
use mpl_core::{
    accounts::BaseAssetV1,
    instructions::CreateV2CpiBuilder,
    ID as MPL_CORE_ID,
};

// Run `anchor keys sync` before build/deploy to replace this sample ID with the
// program keypair generated for this workspace. Set the resulting address in the
// backend EVENTPASS_PROGRAM_ID environment variable.
declare_id!("C9PLf3qMCVqtUCJtEBy8NCcseNp3KTZwFJxAtDdN1bto");

#[program]
pub mod eventpass {
    use super::*;

    pub fn initialize_event(
        ctx: Context<InitializeEvent>,
        event_id: String,
        organizer: Pubkey,
    ) -> Result<()> {
        require!(event_id.as_bytes().len() <= 64, EventPassError::InvalidEventId);
        require_keys_eq!(ctx.accounts.authority.key(), organizer, EventPassError::Unauthorized);
        let event = &mut ctx.accounts.event;
        event.event_id = event_id;
        event.authority = ctx.accounts.authority.key();
        event.organizer = organizer;
        event.bump = ctx.bumps.event;
        Ok(())
    }

    pub fn mint_ticket(
        ctx: Context<MintTicket>,
        event_id: String,
        ticket_id: String,
        name: String,
        uri: String,
    ) -> Result<()> {
        require!(ticket_id.as_bytes().len() <= 64, EventPassError::InvalidTicketId);
        require!(name.as_bytes().len() <= 64, EventPassError::InvalidMetadata);
        require!(uri.as_bytes().len() <= 200, EventPassError::InvalidMetadata);
        require_keys_eq!(ctx.accounts.event.authority, ctx.accounts.authority.key(), EventPassError::Unauthorized);

        let asset_bump = ctx.bumps.asset;
        let ticket_id_seed = ticket_id.as_bytes();
        let asset_seeds: &[&[u8]] = &[b"asset", ticket_id_seed, &[asset_bump]];
        let asset_info = ctx.accounts.asset.to_account_info();
        let authority_info = ctx.accounts.authority.to_account_info();
        let owner_info = ctx.accounts.owner.to_account_info();
        let system_info = ctx.accounts.system_program.to_account_info();
        let core_info = ctx.accounts.mpl_core_program.to_account_info();

        CreateV2CpiBuilder::new(&core_info)
            .asset(&asset_info)
            .collection(None)
            .authority(None)
            .payer(&authority_info)
            .owner(Some(&owner_info))
            .update_authority(Some(&authority_info))
            .system_program(&system_info)
            .name(name)
            .uri(uri)
            .invoke_signed(&[asset_seeds])?;

        let record = &mut ctx.accounts.ticket_record;
        record.event = ctx.accounts.event.key();
        record.asset = ctx.accounts.asset.key();
        record.owner = ctx.accounts.owner.key();
        record.ticket_id = ticket_id;
        record.checked_in = false;
        record.bump = ctx.bumps.ticket_record;
        Ok(())
    }

    pub fn check_in(
        ctx: Context<CheckIn>,
        event_id: String,
        ticket_id: String,
    ) -> Result<()> {
        require_keys_eq!(ctx.accounts.scanner.key(), ctx.accounts.event.organizer, EventPassError::Unauthorized);
        require_keys_eq!(ctx.accounts.ticket_record.event, ctx.accounts.event.key(), EventPassError::WrongEvent);
        require_keys_eq!(ctx.accounts.ticket_record.asset, ctx.accounts.asset.key(), EventPassError::WrongAsset);
        require_keys_eq!(ctx.accounts.ticket_record.owner, ctx.accounts.asset.owner, EventPassError::WrongOwner);
        require!(!ctx.accounts.ticket_record.checked_in, EventPassError::AlreadyCheckedIn);
        ctx.accounts.ticket_record.checked_in = true;
        Ok(())
    }
}

#[derive(Accounts)]
#[instruction(event_id: String)]
pub struct InitializeEvent<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        init,
        payer = authority,
        space = EventPassEvent::SPACE,
        seeds = [b"event", event_id.as_bytes()],
        bump
    )]
    pub event: Account<'info, EventPassEvent>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(event_id: String, ticket_id: String)]
pub struct MintTicket<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(seeds = [b"event", event_id.as_bytes()], bump = event.bump, has_one = authority)]
    pub event: Account<'info, EventPassEvent>,
    #[account(
        init,
        payer = authority,
        space = TicketRecord::SPACE,
        seeds = [b"ticket", ticket_id.as_bytes()],
        bump
    )]
    pub ticket_record: Account<'info, TicketRecord>,
    /// CHECK: Address is constrained to the program-derived Core Asset signer.
    #[account(mut, seeds = [b"asset", ticket_id.as_bytes()], bump)]
    pub asset: UncheckedAccount<'info>,
    /// CHECK: Metaplex Core validates and stores this owner address.
    pub owner: UncheckedAccount<'info>,
    /// CHECK: Program address is constrained to the official MPL Core program.
    #[account(address = MPL_CORE_ID)]
    pub mpl_core_program: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(event_id: String, ticket_id: String)]
pub struct CheckIn<'info> {
    pub scanner: Signer<'info>,
    #[account(seeds = [b"event", event_id.as_bytes()], bump = event.bump)]
    pub event: Account<'info, EventPassEvent>,
    #[account(mut, seeds = [b"ticket", ticket_id.as_bytes()], bump = ticket_record.bump)]
    pub ticket_record: Account<'info, TicketRecord>,
    #[account(owner = MPL_CORE_ID)]
    pub asset: Account<'info, BaseAssetV1>,
}

#[account]
pub struct EventPassEvent {
    pub event_id: String,
    pub authority: Pubkey,
    pub bump: u8,
}
impl EventPassEvent {
    pub const SPACE: usize = 8 + 4 + 64 + 32 + 32 + 1;
}

#[account]
pub struct TicketRecord {
    pub event: Pubkey,
    pub asset: Pubkey,
    pub owner: Pubkey,
    pub ticket_id: String,
    pub checked_in: bool,
    pub bump: u8,
}
impl TicketRecord {
    pub const SPACE: usize = 8 + 32 + 32 + 32 + 4 + 64 + 1 + 1;
}

#[error_code]
pub enum EventPassError {
    #[msg("Event identifier is invalid.")]
    InvalidEventId,
    #[msg("Ticket identifier is invalid.")]
    InvalidTicketId,
    #[msg("Asset metadata is invalid.")]
    InvalidMetadata,
    #[msg("Signer is not authorized for this event.")]
    Unauthorized,
    #[msg("Ticket belongs to another event.")]
    WrongEvent,
    #[msg("Ticket asset does not match the recorded asset.")]
    WrongAsset,
    #[msg("Ticket owner does not match the Core asset owner.")]
    WrongOwner,
    #[msg("Ticket has already been checked in.")]
    AlreadyCheckedIn,
}
