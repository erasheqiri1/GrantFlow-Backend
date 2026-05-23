-- Migration: Email Verification
-- Run this once against your PostgreSQL database

-- 1. Shto kolonën email_verified te tabela public.users
--    DEFAULT TRUE — të gjithë userat ekzistues konsiderohen të verifikuar
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Krijo tabelën e tokenave të verifikimit
CREATE TABLE IF NOT EXISTS public.email_verification_tokens (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token      VARCHAR(200) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
