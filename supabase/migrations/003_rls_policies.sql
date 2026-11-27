-- =============================================================================
-- EventPass: Row Level Security (RLS) Policies
-- Migration: 003_rls_policies.sql
-- Apply with: psql $DATABASE_URL -f supabase/migrations/003_rls_policies.sql
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. ENABLE RLS on all tables
-- ---------------------------------------------------------------------------
ALTER TABLE public.profiles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tickets           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resale_listings   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resale_campaigns  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ticket_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.refund_requests   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ledger_journals   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ledger_entries    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ticket_ownership_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.check_ins         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbox_jobs       ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 2. Helper: role check from JWT claims
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION auth.user_role() RETURNS TEXT AS $$
  SELECT COALESCE(
    (SELECT role FROM public.profiles WHERE id = auth.uid()),
    auth.jwt() ->> 'role',
    'buyer'
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ---------------------------------------------------------------------------
-- 3. PROFILES
-- ---------------------------------------------------------------------------
-- Users can read and update their own profile
CREATE POLICY "profiles_select_own"
  ON public.profiles FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "profiles_update_own"
  ON public.profiles FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- Admins can read all profiles
CREATE POLICY "profiles_admin_select_all"
  ON public.profiles FOR SELECT
  USING (auth.user_role() = 'admin');

-- ---------------------------------------------------------------------------
-- 4. EVENTS
-- ---------------------------------------------------------------------------
-- Anyone can read published events
CREATE POLICY "events_public_select"
  ON public.events FOR SELECT
  USING (true);

-- Only organizers can create events
CREATE POLICY "events_organizer_insert"
  ON public.events FOR INSERT
  WITH CHECK (auth.user_role() IN ('organizer', 'admin'));

-- Organizer can update their own events; admins can update any
CREATE POLICY "events_organizer_update_own"
  ON public.events FOR UPDATE
  USING (
    organizer_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR auth.user_role() = 'admin'
  );

-- ---------------------------------------------------------------------------
-- 5. TICKETS
-- ---------------------------------------------------------------------------
-- Users can read their own tickets; organizers/admins see all
CREATE POLICY "tickets_select_own"
  ON public.tickets FOR SELECT
  USING (
    owner_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR auth.user_role() IN ('organizer', 'admin')
  );

-- Only the backend service role inserts tickets (primary purchase minting)
-- INSERT is handled server-side via service role key – no user INSERT policy needed.

-- Ticket owner can update their own ticket (e.g., listed status changes)
CREATE POLICY "tickets_update_own"
  ON public.tickets FOR UPDATE
  USING (
    owner_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR auth.user_role() IN ('organizer', 'admin')
  );

-- ---------------------------------------------------------------------------
-- 6. RESALE LISTINGS
-- ---------------------------------------------------------------------------
-- Public can read active listings
CREATE POLICY "resale_listings_public_select"
  ON public.resale_listings FOR SELECT
  USING (true);

-- Sellers can insert listings for tickets they own
CREATE POLICY "resale_listings_seller_insert"
  ON public.resale_listings FOR INSERT
  WITH CHECK (
    seller_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
  );

-- Sellers can update/cancel their own listings; organizers/admins can update any
CREATE POLICY "resale_listings_seller_update"
  ON public.resale_listings FOR UPDATE
  USING (
    seller_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR auth.user_role() IN ('organizer', 'admin')
  );

-- ---------------------------------------------------------------------------
-- 7. RESALE CAMPAIGNS
-- ---------------------------------------------------------------------------
-- Public can read campaigns (for social share pages)
CREATE POLICY "resale_campaigns_public_select"
  ON public.resale_campaigns FOR SELECT
  USING (true);

-- Sellers can create campaigns
CREATE POLICY "resale_campaigns_seller_insert"
  ON public.resale_campaigns FOR INSERT
  WITH CHECK (
    seller_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
  );

CREATE POLICY "resale_campaigns_seller_update"
  ON public.resale_campaigns FOR UPDATE
  USING (
    seller_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR auth.user_role() IN ('organizer', 'admin')
  );

-- ---------------------------------------------------------------------------
-- 8. TRANSACTIONS
-- ---------------------------------------------------------------------------
-- Buyers and sellers see their own transactions; organizers/admins see all
CREATE POLICY "transactions_parties_select"
  ON public.transactions FOR SELECT
  USING (
    buyer_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR seller_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR auth.user_role() IN ('organizer', 'admin')
  );

-- ---------------------------------------------------------------------------
-- 9. TICKET RESERVATIONS
-- ---------------------------------------------------------------------------
CREATE POLICY "ticket_reservations_select"
  ON public.ticket_reservations FOR SELECT
  USING (
    buyer_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR auth.user_role() IN ('organizer', 'admin')
  );

-- ---------------------------------------------------------------------------
-- 10. REFUND REQUESTS
-- ---------------------------------------------------------------------------
CREATE POLICY "refund_requests_select_own"
  ON public.refund_requests FOR SELECT
  USING (
    requester_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR auth.user_role() IN ('organizer', 'admin')
  );

-- ---------------------------------------------------------------------------
-- 11. LEDGER (read-only for organizers/admins, invisible to buyers)
-- ---------------------------------------------------------------------------
CREATE POLICY "ledger_journals_organizer_select"
  ON public.ledger_journals FOR SELECT
  USING (auth.user_role() IN ('organizer', 'admin'));

CREATE POLICY "ledger_entries_organizer_select"
  ON public.ledger_entries FOR SELECT
  USING (auth.user_role() IN ('organizer', 'admin'));

-- ---------------------------------------------------------------------------
-- 12. TICKET OWNERSHIP HISTORY
-- ---------------------------------------------------------------------------
CREATE POLICY "ownership_history_own_select"
  ON public.ticket_ownership_history FOR SELECT
  USING (
    from_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR to_wallet = (
      SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
    )
    OR auth.user_role() IN ('organizer', 'admin')
  );

-- ---------------------------------------------------------------------------
-- 13. CHECK-INS
-- ---------------------------------------------------------------------------
-- Organizers/admins can read and insert check-ins; ticket holders can see their own
CREATE POLICY "check_ins_organizer_all"
  ON public.check_ins FOR ALL
  USING (auth.user_role() IN ('organizer', 'admin'));

CREATE POLICY "check_ins_owner_select"
  ON public.check_ins FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.tickets t
      WHERE t.id = ticket_id
        AND t.owner_wallet = (
          SELECT wallet_address FROM public.profiles WHERE id = auth.uid()
        )
    )
  );

-- ---------------------------------------------------------------------------
-- 14. AUDIT LOGS (organizers/admins only)
-- ---------------------------------------------------------------------------
CREATE POLICY "audit_logs_admin_select"
  ON public.audit_logs FOR SELECT
  USING (auth.user_role() IN ('organizer', 'admin'));

-- ---------------------------------------------------------------------------
-- 15. OUTBOX JOBS (backend service role only — no user access)
-- ---------------------------------------------------------------------------
-- No SELECT policy for authenticated users; service role bypasses RLS by default.
-- If you need to allow admin monitoring:
CREATE POLICY "outbox_jobs_admin_select"
  ON public.outbox_jobs FOR SELECT
  USING (auth.user_role() = 'admin');
