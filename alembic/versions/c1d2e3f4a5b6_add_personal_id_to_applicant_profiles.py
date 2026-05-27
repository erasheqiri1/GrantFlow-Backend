"""add personal_id to applicant_profiles

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6, b8e2f1a94c30
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str]] = ('a1b2c3d4e5f6', 'b8e2f1a94c30')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'applicant_profiles',
        sa.Column('personal_id', sa.String(20), nullable=True),
        schema='public',
    )


def downgrade() -> None:
    op.drop_column('applicant_profiles', 'personal_id', schema='public')
