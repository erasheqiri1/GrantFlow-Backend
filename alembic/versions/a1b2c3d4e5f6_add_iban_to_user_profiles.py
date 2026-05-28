"""add iban to user_profiles

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-05-28 22:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, Sequence[str]] = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'user_profiles',
        sa.Column('iban', sa.String(34), nullable=True),
        schema='public'
    )


def downgrade() -> None:
    op.drop_column('user_profiles', 'iban', schema='public')
