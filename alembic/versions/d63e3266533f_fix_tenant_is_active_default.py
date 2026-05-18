"""fix tenant is_active default

Revision ID: d63e3266533f
Revises: 3e22a7665629
Create Date: 2026-05-18 16:01:00.983085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd63e3266533f'
down_revision: Union[str, Sequence[str], None] = '3e22a7665629'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'tenants', 'is_active',
        existing_type=sa.Boolean(),
        server_default=sa.text('false'),
        schema='public'
    )


def downgrade() -> None:
    op.alter_column(
        'tenants', 'is_active',
        existing_type=sa.Boolean(),
        server_default=sa.text('true'),
        schema='public'
    )
