# EventPass Anchor Program

This workspace contains the Devnet program source. The checked-in ID in
`programs/eventpass/src/lib.rs` is a sample ID; it is not a deployment.
Generate the deployment keypair, then sync the source/config ID before building.

## Deploy to Devnet

1. Install compatible Rust 1.89+, Solana CLI, and Anchor CLI 0.32.1.
2. From this directory, run `anchor keys sync`.
3. Run `anchor build` and review the generated IDL under `target/idl/eventpass.json`.
4. Point Solana CLI at Devnet and fund the deployment wallet with Devnet SOL.
5. Run `anchor deploy`.
6. Set backend `EVENTPASS_PROGRAM_ID` to the deployed program address and
   `BACKEND_SOLANA_PRIVATE_KEY` to the authority keypair used by the backend.
7. Apply `supabase/migrations/006_live_payments_and_assets.sql` before enabling
   primary PayFast checkout.

The backend currently supports event initialization, primary ticket minting, and
single-use on-chain check-in through this program. Resale Core-asset transfers
remain disabled until the program adds and tests a transfer-delegate flow. Do not
enable PayFast resale checkouts before then.

The browser and Supabase service-role secrets must stay out of this workspace.
Use Vercel's encrypted environment-variable settings for backend credentials.
