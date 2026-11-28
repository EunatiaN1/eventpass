-- Real primary checkout waits for verified payment before creating a Core asset.
ALTER TABLE public.tickets
    ALTER COLUMN asset_address DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tickets_order_reference
    ON public.tickets (order_reference);
