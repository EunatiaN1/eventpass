-- EventPass Full Platform Migration (Phase 2+)
-- Adds organizer resale controls, multi-ticket social campaigns, 75% unsold-ticket refunds,
-- immutable double-entry ledger, QR credentials, check-ins, outbox jobs, and audit logs.

-- 1. Extend events with timezone, resale caps, and 15-day refund policy fields
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS venue TEXT NOT NULL DEFAULT 'Cape Town Stadium',
    ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'Africa/Johannesburg',
    ADD COLUMN IF NOT EXISTS ticket_price_zar INTEGER NOT NULL DEFAULT 500 CHECK (ticket_price_zar >= 0),
    ADD COLUMN IF NOT EXISTS max_resale_price_zar INTEGER CHECK (max_resale_price_zar IS NULL OR max_resale_price_zar > 0),
    ADD COLUMN IF NOT EXISTS max_resale_markup_bps INTEGER DEFAULT 1000 CHECK (max_resale_markup_bps IS NULL OR max_resale_markup_bps >= 0),
    ADD COLUMN IF NOT EXISTS marketplace_fee_bps INTEGER NOT NULL DEFAULT 500 CHECK (marketplace_fee_bps = 500),
    ADD COLUMN IF NOT EXISTS resale_start_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS resale_cutoff_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS refund_window_open_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS refund_cutoff_days INTEGER NOT NULL DEFAULT 15 CHECK (refund_cutoff_days >= 15);

-- 2. Extend tickets with original purchaser, tier, and check-in metadata
ALTER TABLE tickets
    ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'General Admission',
    ADD COLUMN IF NOT EXISTS original_buyer_wallet TEXT,
    ADD COLUMN IF NOT EXISTS order_reference TEXT,
    ADD COLUMN IF NOT EXISTS checked_in_at TIMESTAMPTZ;

-- 3. Resale Campaigns (social-media sharing layer over individual ticket listings)
CREATE TABLE IF NOT EXISTS resale_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    seller_wallet TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'sold_out', 'cancelled', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Link individual resale listings to a campaign
ALTER TABLE resale_listings
    ADD COLUMN IF NOT EXISTS campaign_id UUID REFERENCES resale_campaigns(id) ON DELETE SET NULL;

-- 4. Extend transactions with checkout method, fee breakdown, and listing/campaign links
ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS listing_id UUID REFERENCES resale_listings(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS payment_method TEXT DEFAULT 'card',
    ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'ZAR',
    ADD COLUMN IF NOT EXISTS marketplace_fee_amount BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS seller_proceeds_amount BIGINT NOT NULL DEFAULT 0;

-- 5. Unsold-Ticket Refund Requests (75% of original price, mutually exclusive with resale)
CREATE TABLE IF NOT EXISTS refund_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL UNIQUE REFERENCES tickets(id) ON DELETE CASCADE,
    requester_wallet TEXT NOT NULL,
    original_price_zar INTEGER NOT NULL CHECK (original_price_zar >= 0),
    refund_amount_zar INTEGER NOT NULL CHECK (refund_amount_zar >= 0),
    retained_amount_zar INTEGER NOT NULL CHECK (retained_amount_zar >= 0),
    status TEXT NOT NULL DEFAULT 'approved'
        CHECK (status IN ('pending', 'approved', 'paid', 'rejected', 'failed')),
    payout_due_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. Immutable Double-Entry Ledger
CREATE TABLE IF NOT EXISTS ledger_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL CHECK (account_type IN ('asset', 'liability', 'revenue', 'expense'))
);

CREATE TABLE IF NOT EXISTS ledger_journals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'ZAR',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_id UUID NOT NULL REFERENCES ledger_journals(id) ON DELETE CASCADE,
    account_code TEXT NOT NULL REFERENCES ledger_accounts(code),
    direction TEXT NOT NULL CHECK (direction IN ('debit', 'credit')),
    amount BIGINT NOT NULL CHECK (amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. Ticket Ownership History & Audit Logs
CREATE TABLE IF NOT EXISTS ticket_ownership_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    from_wallet TEXT,
    to_wallet TEXT,
    action TEXT NOT NULL CHECK (action IN ('issued', 'transferred', 'refunded', 'checked_in')),
    reference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS check_ins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL UNIQUE REFERENCES tickets(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    credential_version INTEGER NOT NULL,
    scanner_id TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('accepted', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outbox_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'completed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
