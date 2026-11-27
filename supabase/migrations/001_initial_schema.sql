-- EventPass Initial Database Schema (Solana Devnet MVP)
-- Enforces one authoritative ownership/listing/reservation state per ticket.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Events
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    event_date TIMESTAMPTZ NOT NULL,
    organizer_wallet TEXT NOT NULL,
    resale_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Tickets (each ticket is an individually identifiable Metaplex Core asset)
CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    asset_address TEXT NOT NULL UNIQUE,
    owner_wallet TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'issued'
        CHECK (status IN ('issued', 'listed', 'reserved', 'sold', 'refunded', 'checked_in')),
    original_price_zar INTEGER NOT NULL CHECK (original_price_zar >= 0),
    credential_version INTEGER NOT NULL DEFAULT 1 CHECK (credential_version >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tickets_event_id ON tickets (event_id);
CREATE INDEX IF NOT EXISTS idx_tickets_owner_wallet ON tickets (owner_wallet);

-- 3. Resale Listings
CREATE TABLE IF NOT EXISTS resale_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    seller_wallet TEXT NOT NULL,
    asking_price_zar INTEGER NOT NULL CHECK (asking_price_zar > 0),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'reserved', 'sold', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Prevent a ticket from having more than one active or reserved listing at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_resale_listings_one_active_per_ticket
    ON resale_listings (ticket_id)
    WHERE status IN ('active', 'reserved');

-- 4. Transactions (payment records & idempotency source of truth)
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_reference TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL CHECK (provider IN ('payfast', 'paystack', 'x402')),
    amount BIGINT NOT NULL CHECK (amount >= 0),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'settled', 'failed')),
    ticket_id UUID REFERENCES tickets(id) ON DELETE SET NULL,
    buyer_wallet TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transactions_ticket_id ON transactions (ticket_id);

-- 5. Ticket Reservations (at most one reservation row per ticket)
CREATE TABLE IF NOT EXISTS ticket_reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL UNIQUE REFERENCES tickets(id) ON DELETE CASCADE,
    buyer_wallet TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'expired', 'completed', 'cancelled')),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Explicit partial unique index reinforcing single active reservation per ticket
CREATE UNIQUE INDEX IF NOT EXISTS idx_ticket_reservations_one_active_per_ticket
    ON ticket_reservations (ticket_id)
    WHERE status = 'active';
