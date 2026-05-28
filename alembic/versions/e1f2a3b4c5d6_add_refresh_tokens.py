"""add refresh_tokens table

Revision ID: e1f2a3b4c5d6
Revises: c1d2e3f4a5b6
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str]] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'refresh_tokens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_slug', sa.String(100), nullable=True),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='public',
    )
    op.create_index('ix_public_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'], schema='public')
    op.create_index('ix_public_refresh_tokens_user_id', 'refresh_tokens', ['user_id'], schema='public')


def downgrade() -> None:
    op.drop_index('ix_public_refresh_tokens_user_id', table_name='refresh_tokens', schema='public')
    op.drop_index('ix_public_refresh_tokens_token_hash', table_name='refresh_tokens', schema='public')
    op.drop_table('refresh_tokens', schema='public')
