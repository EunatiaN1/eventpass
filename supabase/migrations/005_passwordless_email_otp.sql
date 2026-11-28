-- Passwordless email OTP support for databases where the original schema is already applied.
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address TEXT NOT NULL UNIQUE,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'buyer'
        CHECK (role IN ('buyer', 'organizer', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS wallet_address TEXT,
    ADD COLUMN IF NOT EXISTS email TEXT,
    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'buyer',
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_email_lower
    ON public.profiles (lower(email)) WHERE email IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.otp_challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed BOOLEAN NOT NULL DEFAULT FALSE,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.otp_challenges
    ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE public.otp_challenges ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.otp_challenges FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.otp_challenges TO service_role;
GRANT ALL ON public.profiles TO service_role;
