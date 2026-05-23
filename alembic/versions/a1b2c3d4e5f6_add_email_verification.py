"""add email verification column and table

Revision ID: a1b2c3d4e5f6
Revises: f7a3c9e1b402
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f7a3c9e1b402'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Shto kolonën email_verified te tabela users
    # DEFAULT TRUE — të gjithë userat ekzistues konsiderohen të verifikuar
    op.add_column(
        'users',
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='true'),
        schema='public',
    )

    # Krijo tabelën e tokenave të verifikimit
    op.create_table(
        'email_verification_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token', sa.String(length=200), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_id'], ['public.users.id'],
            name='fk_email_verification_tokens_user_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token', name='uq_email_verification_token'),
        schema='public',
    )


def downgrade() -> None:
    op.drop_table('email_verification_tokens', schema='public')
    op.drop_column('users', 'email_verified', schema='public')
