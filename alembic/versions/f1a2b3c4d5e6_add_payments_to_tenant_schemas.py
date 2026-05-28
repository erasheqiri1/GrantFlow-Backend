"""add payments table to tenant schemas

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-05-28 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str]] = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def get_tenant_schemas(conn):
    """Merr të gjitha schemat tenant_ nga databaza."""
    result = conn.execute(text("""
        SELECT schema_name FROM information_schema.schemata
        WHERE schema_name LIKE 'tenant_%'
        ORDER BY schema_name
    """))
    return [row[0] for row in result]


def upgrade() -> None:
    conn = op.get_bind()
    schemas = get_tenant_schemas(conn)

    for schema in schemas:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS "{schema}".payments (
                id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                application_id UUID NOT NULL
                    REFERENCES "{schema}".applications(id) ON DELETE CASCADE,
                amount         NUMERIC(12, 2),
                currency       VARCHAR(10) NOT NULL DEFAULT 'EUR',
                status         VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                               CHECK (status IN ('PENDING', 'PAID')),
                reference      VARCHAR(200),
                paid_at        TIMESTAMPTZ,
                paid_by        UUID REFERENCES public.users(id),
                note           VARCHAR(500),
                created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_payment_application_{schema} UNIQUE (application_id)
            )
        """))
        print(f"  [OK] payments table created in {schema}")


def downgrade() -> None:
    conn = op.get_bind()
    schemas = get_tenant_schemas(conn)
    for schema in schemas:
        conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".payments CASCADE'))
