from sqlalchemy import text
from sqlalchemy.orm import Session

TENANT_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS "{schema}".user_roles (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    role_id    UUID NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_role UNIQUE (user_id, role_id)
);
CREATE TABLE IF NOT EXISTS "{schema}".grants (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title          VARCHAR(200) NOT NULL,
    description    TEXT,
    budget         NUMERIC(12,2),
    currency       VARCHAR(10) NOT NULL DEFAULT 'EUR',
    deadline       TIMESTAMPTZ,
    max_applicants INTEGER,
    status         VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    applicant_type VARCHAR(50) NOT NULL DEFAULT 'ANY',
    ai_weight      NUMERIC(3,2) NOT NULL DEFAULT 0.60,
    created_by     UUID NOT NULL REFERENCES public.users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS "{schema}".criteria (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id    UUID NOT NULL REFERENCES "{schema}".grants(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    weight      NUMERIC(3,2) NOT NULL,
    min_value   NUMERIC(5,2),
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_grant_criteria_name UNIQUE (grant_id, name)
);
CREATE TABLE IF NOT EXISTS "{schema}".grant_tags (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id UUID NOT NULL REFERENCES "{schema}".grants(id) ON DELETE CASCADE,
    tag      VARCHAR(50) NOT NULL,
    CONSTRAINT uq_grant_tag UNIQUE (grant_id, tag)
);
CREATE TABLE IF NOT EXISTS "{schema}".application_questions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id      UUID NOT NULL REFERENCES "{schema}".grants(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type VARCHAR(50) NOT NULL DEFAULT 'LONG_TEXT',
    is_required   BOOLEAN NOT NULL DEFAULT TRUE,
    order_no      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS "{schema}".applications (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id          UUID NOT NULL REFERENCES "{schema}".grants(id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    status            VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    motivation_letter TEXT,
    submitted_at      TIMESTAMPTZ,
    decided_by        UUID REFERENCES public.users(id),
    decided_at        TIMESTAMPTZ,
    decision_reason   TEXT,
    assigned_to       UUID REFERENCES public.users(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_application_grant_user UNIQUE (grant_id, user_id)
);
CREATE TABLE IF NOT EXISTS "{schema}".application_answers (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    question_id    UUID NOT NULL REFERENCES "{schema}".application_questions(id) ON DELETE CASCADE,
    answer_text    TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_application_question_answer UNIQUE (application_id, question_id)
);
CREATE TABLE IF NOT EXISTS "{schema}".cvs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    file_path      VARCHAR(500) NOT NULL,
    file_name      VARCHAR(200) NOT NULL,
    parsed_text    TEXT,
    uploaded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cv_application UNIQUE (application_id)
);
CREATE TABLE IF NOT EXISTS "{schema}".attachments (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    file_path      VARCHAR(500) NOT NULL,
    file_name      VARCHAR(200) NOT NULL,
    file_type      VARCHAR(100),
    size_bytes     INTEGER,
    uploaded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS "{schema}".ai_scores (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    ai_score       INTEGER,
    justification  TEXT,
    final_score    NUMERIC(5,2),
    rank_position  INTEGER,
    model_used     VARCHAR(100),
    is_cached      BOOLEAN NOT NULL DEFAULT FALSE,
    scored_at      TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_score_application UNIQUE (application_id)
);
CREATE TABLE IF NOT EXISTS "{schema}".commissioner_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    commissioner_id UUID NOT NULL REFERENCES public.users(id),
    criteria_id     UUID NOT NULL REFERENCES "{schema}".criteria(id) ON DELETE CASCADE,
    score           INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    comment         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_commissioner_score UNIQUE (application_id, criteria_id)
);
CREATE TABLE IF NOT EXISTS "{schema}".commissioner_decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    commissioner_id UUID NOT NULL REFERENCES public.users(id),
    decision        VARCHAR(20) NOT NULL,
    reason          TEXT,
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_decision_application UNIQUE (application_id)
);
CREATE TABLE IF NOT EXISTS "{schema}".committees (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id   UUID NOT NULL REFERENCES "{schema}".grants(id) ON DELETE CASCADE,
    name       VARCHAR(200) NOT NULL,
    created_by UUID NOT NULL REFERENCES public.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS "{schema}".committee_members (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    committee_id UUID NOT NULL REFERENCES "{schema}".committees(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_committee_member UNIQUE (committee_id, user_id)
);
CREATE TABLE IF NOT EXISTS "{schema}".invitations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(200) NOT NULL,
    role_id     UUID NOT NULL REFERENCES public.roles(id),
    invited_by  UUID NOT NULL REFERENCES public.users(id),
    token       VARCHAR(200) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    is_used     BOOLEAN NOT NULL DEFAULT FALSE,
    accepted_at TIMESTAMPTZ,
    accepted_by UUID REFERENCES public.users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS "{schema}".notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title      VARCHAR(200) NOT NULL,
    message    TEXT NOT NULL,
    type       VARCHAR(50) NOT NULL,
    is_read    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS "{schema}".email_logs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    to_email   VARCHAR(200) NOT NULL,
    subject    VARCHAR(300) NOT NULL,
    body       TEXT,
    status     VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    sent_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS "{schema}".audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES public.users(id),
    action      VARCHAR(100) NOT NULL,
    resource    VARCHAR(100) NOT NULL,
    resource_id UUID,
    old_value   JSONB,
    new_value   JSONB,
    ip_address  VARCHAR(50),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS "{schema}".grant_recommendations (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    grant_id   UUID NOT NULL REFERENCES "{schema}".grants(id) ON DELETE CASCADE,
    score      NUMERIC(5,2) NOT NULL,
    reason     TEXT,
    model_used VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_grant_recommendation UNIQUE (user_id, grant_id)
);
CREATE TABLE IF NOT EXISTS "{schema}".application_status_updates (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    old_status     VARCHAR(50) NOT NULL,
    new_status     VARCHAR(50) NOT NULL,
    changed_by     UUID NOT NULL REFERENCES public.users(id),
    changed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def create_tenant_schema(db: Session, tenant_slug: str) -> None:
    db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{tenant_slug}"'))
    sql = TENANT_TABLES_SQL.replace('"{schema}"', f'"{tenant_slug}"')
    db.execute(text(sql))
    db.commit()
    print(f"✓ Schema '{tenant_slug}' u krijua me 20 tabela.")


def drop_tenant_schema(db: Session, tenant_slug: str) -> None:
    db.execute(text(f'DROP SCHEMA IF EXISTS "{tenant_slug}" CASCADE'))
    db.commit()


def set_tenant_search_path(db: Session, tenant_slug: str) -> None:
    db.execute(text(f'SET search_path TO "{tenant_slug}", public'))