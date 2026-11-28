-- Atomic, idempotent settlement for the explicitly simulated primary checkout.
-- Called only by FastAPI using the Supabase service role.
CREATE OR REPLACE FUNCTION public.settle_mock_payment(
    p_ticket_id TEXT,
    p_payment_method TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_ticket tickets%ROWTYPE;
    v_transaction transactions%ROWTYPE;
    v_ticket_ids JSONB;
    v_idempotent BOOLEAN := FALSE;
BEGIN
    IF p_payment_method NOT IN ('eft', 'card', 'x402') THEN
        RAISE EXCEPTION 'Unsupported simulated payment method.';
    END IF;

    SELECT * INTO v_ticket
      FROM tickets
     WHERE id::TEXT = p_ticket_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Ticket not found.';
    END IF;

    SELECT * INTO v_transaction
      FROM transactions
     WHERE payment_reference = v_ticket.order_reference
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Checkout transaction not found.';
    END IF;
    IF v_transaction.payment_method IS DISTINCT FROM p_payment_method THEN
        RAISE EXCEPTION 'Payment method does not match this checkout.';
    END IF;

    IF v_transaction.status = 'settled' THEN
        IF EXISTS (
            SELECT 1 FROM tickets
             WHERE order_reference = v_ticket.order_reference
               AND status <> 'sold'
        ) THEN
            RAISE EXCEPTION 'Already settled checkout has inconsistent tickets.';
        END IF;
        v_idempotent := TRUE;
    ELSIF v_transaction.status = 'pending' THEN
        IF EXISTS (
            SELECT 1 FROM tickets
             WHERE order_reference = v_ticket.order_reference
               AND status <> 'reserved'
        ) THEN
            RAISE EXCEPTION 'Checkout contains a ticket that is not reserved.';
        END IF;
        UPDATE tickets
           SET status = 'sold'
         WHERE order_reference = v_ticket.order_reference
           AND status = 'reserved';
        UPDATE transactions
           SET status = 'settled'
         WHERE id = v_transaction.id;
    ELSE
        RAISE EXCEPTION 'Checkout is not pending.';
    END IF;

    SELECT COALESCE(jsonb_agg(id::TEXT ORDER BY created_at, id), '[]'::JSONB)
      INTO v_ticket_ids
      FROM tickets
     WHERE order_reference = v_ticket.order_reference;

    RETURN jsonb_build_object(
        'status', CASE WHEN v_idempotent THEN 'already_settled' ELSE 'settled' END,
        'payment_reference', v_transaction.payment_reference,
        'ticket_ids', v_ticket_ids,
        'amount_zar', v_transaction.amount,
        'idempotent', v_idempotent
    );
END;
$$;

REVOKE ALL ON FUNCTION public.settle_mock_payment(TEXT, TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.settle_mock_payment(TEXT, TEXT) TO service_role;
