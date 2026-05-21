"""add public audit_logs table

Revision ID: f7a3c9e1b402
Revises: d63e3266533f
Create Date: 2026-05-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7a3c9e1b402'
down_revision: Union[str, None] = 'd63e3266533f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity', sa.String(length=100), nullable=True),
        sa.Column('entity_id', sa.UUID(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_id'], ['public.users.id'],
            name='fk_audit_logs_user_id',
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['public.tenants.id'],
            name='fk_audit_logs_tenant_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
        schema='public',
    )
    op.create_index(
        'ix_audit_logs_user_id',
        'audit_logs',
        ['user_id'],
        schema='public',
    )
    op.create_index(
        'ix_audit_logs_created_at',
        'audit_logs',
        ['created_at'],
        schema='public',
    )


def downgrade() -> None:
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs', schema='public')
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs', schema='public')
    op.drop_table('audit_logs', schema='public')
