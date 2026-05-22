from sqlalchemy import text
from sqlalchemy.orm import Session

TENANT_TABLES_SQL = """

-- 1. grants
CREATE TABLE IF NOT EXISTS "{schema}".grants (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title          VARCHAR(200) NOT NULL,
    description    TEXT,
    budget         NUMERIC(12, 2),
    currency       VARCHAR(10) NOT NULL DEFAULT 'EUR',
    grant_value    NUMERIC(12, 2),
    deadline       TIMESTAMPTZ,
    max_applicants INTEGER,
    status         VARCHAR(50) NOT NULL DEFAULT 'DRAFT'
                   CHECK (status IN ('DRAFT', 'PUBLISHED', 'CLOSED')),
    applicant_type VARCHAR(50) NOT NULL DEFAULT 'ANY'
                   CHECK (applicant_type IN ('ANY', 'STUDENT', 'BUSINESS', 'ORGANIZATION', 'INDIVIDUAL')),
    ai_weight      NUMERIC(5, 2) NOT NULL DEFAULT 0.60
                   CHECK (ai_weight >= 0 AND ai_weight <= 1),
    created_by     UUID NOT NULL REFERENCES public.users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. criteria
CREATE TABLE IF NOT EXISTS "{schema}".criteria (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id    UUID NOT NULL REFERENCES "{schema}".grants(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    weight      NUMERIC(5, 2) NOT NULL,
    min_value   NUMERIC(5, 2),
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_grant_criteria_name UNIQUE (grant_id, name)
);

-- 3. grant_tags
CREATE TABLE IF NOT EXISTS "{schema}".grant_tags (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id UUID NOT NULL REFERENCES "{schema}".grants(id) ON DELETE CASCADE,
    tag      VARCHAR(50) NOT NULL,
    CONSTRAINT uq_grant_tag UNIQUE (grant_id, tag)
);

-- 4. application_questions
CREATE TABLE IF NOT EXISTS "{schema}".application_questions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id      UUID NOT NULL REFERENCES "{schema}".grants(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type VARCHAR(50) NOT NULL DEFAULT 'LONG_TEXT'
                  CHECK (question_type IN ('TEXT', 'LONG_TEXT', 'NUMBER', 'FILE', 'YES_NO')),
    is_required   BOOLEAN NOT NULL DEFAULT TRUE,
    order_no      INTEGER NOT NULL DEFAULT 1
);

-- 5. applications
CREATE TABLE IF NOT EXISTS "{schema}".applications (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id          UUID NOT NULL REFERENCES "{schema}".grants(id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    status            VARCHAR(50) NOT NULL DEFAULT 'DRAFT'
                      CHECK (status IN ('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED')),
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

-- 6. application_answers
CREATE TABLE IF NOT EXISTS "{schema}".application_answers (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    question_id    UUID NOT NULL REFERENCES "{schema}".application_questions(id) ON DELETE CASCADE,
    answer_text    TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_application_question_answer UNIQUE (application_id, question_id)
);

-- 7. cvs (1:1 me application)
CREATE TABLE IF NOT EXISTS "{schema}".cvs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    file_path      VARCHAR(500) NOT NULL,
    file_name      VARCHAR(200) NOT NULL,
    parsed_text    TEXT,
    uploaded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cv_application UNIQUE (application_id)
);

-- 8. attachments (shume per aplikim)
CREATE TABLE IF NOT EXISTS "{schema}".attachments (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    file_path      VARCHAR(500) NOT NULL,
    file_name      VARCHAR(200) NOT NULL,
    file_type      VARCHAR(100),
    size_bytes     INTEGER,
    uploaded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. ai_scores (1:1 me application)
CREATE TABLE IF NOT EXISTS "{schema}".ai_scores (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id     UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    ai_score           NUMERIC(5, 2),
    justification      TEXT,
    commissioner_score NUMERIC(5, 2),
    final_score        NUMERIC(5, 2),
    rank_position      INTEGER,
    model_used         VARCHAR(100),
    is_cached          BOOLEAN NOT NULL DEFAULT FALSE,
    scored_at          TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_score_application UNIQUE (application_id)
);

-- 10. commissioner_scores
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

-- 11. commissioner_decisions
CREATE TABLE IF NOT EXISTS "{schema}".commissioner_decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID NOT NULL REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
    commissioner_id UUID NOT NULL REFERENCES public.users(id),
    decision        VARCHAR(20) NOT NULL CHECK (decision IN ('APPROVE', 'REJECT')),
    reason          TEXT,
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_decision_application UNIQUE (application_id)
);

-- 12. commissioner_workload
CREATE TABLE IF NOT EXISTS "{schema}".commissioner_workload (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    commissioner_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    assigned_count  INTEGER NOT NULL DEFAULT 0,
    completed_count INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_commissioner_workload UNIQUE (commissioner_id)
);

-- 13. invitations
CREATE TABLE IF NOT EXISTS "{schema}".invitations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(200) NOT NULL,
    role_id     UUID NOT NULL REFERENCES public.roles(id),
    invited_by  UUID NOT NULL REFERENCES public.users(id),
    token       TEXT NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    is_used     BOOLEAN NOT NULL DEFAULT FALSE,
    accepted_at TIMESTAMPTZ,
    accepted_by UUID REFERENCES public.users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 14. notifications
CREATE TABLE IF NOT EXISTS "{schema}".notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title      VARCHAR(200) NOT NULL,
    message    TEXT NOT NULL,
    type       VARCHAR(50) NOT NULL
               CHECK (type IN ('APPLICATION_STATUS', 'DEADLINE', 'INVITE', 'SYSTEM')),
    is_read    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 15. email_logs
CREATE TABLE IF NOT EXISTS "{schema}".email_logs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    to_email   VARCHAR(200) NOT NULL,
    subject    VARCHAR(300) NOT NULL,
    body       TEXT,
    status     VARCHAR(50) NOT NULL DEFAULT 'PENDING'
               CHECK (status IN ('PENDING', 'SENT', 'FAILED')),
    sent_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 16. application_status_updates
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
    """
    Krijon schemën dhe 16 tabelat për tenant të ri.
    Thirret kur SUPER_ADMIN aprovo organizatën.
    """
    schema_name = f"tenant_{tenant_slug.replace('-', '_')}"
    db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
    db.commit()

    sql = TENANT_TABLES_SQL.replace('"{schema}"', f'"{schema_name}"')
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        db.execute(text(stmt))
        db.commit()

    print(f"✓ Schema '{schema_name}' u krijua me {len(statements)} tabela.")


def drop_tenant_schema(db: Session, tenant_slug: str) -> None:
    """Fshin schemën — vetëm për test/dev."""
    schema_name = f"tenant_{tenant_slug.replace('-', '_')}"
    db.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
    db.commit()
    print(f"✓ Schema '{schema_name}' u fshi.")


def set_tenant_search_path(db: Session, tenant_slug: str) -> None:
    """Vendos search_path — thirret nga middleware per çdo request."""
    db.execute(text(f'SET search_path TO "{tenant_slug}", public'))