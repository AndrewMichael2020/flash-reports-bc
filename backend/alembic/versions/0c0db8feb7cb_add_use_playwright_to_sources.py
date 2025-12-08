"""add use_playwright to sources

Revision ID: 0c0db8feb7cb
Revises: faa672a4c13f
Create Date: 2025-12-08 06:15:32.266676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c0db8feb7cb'
down_revision: Union[str, None] = 'faa672a4c13f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add use_playwright column to sources table
    op.add_column('sources', sa.Column('use_playwright', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    # Remove use_playwright column
    op.drop_column('sources', 'use_playwright')
