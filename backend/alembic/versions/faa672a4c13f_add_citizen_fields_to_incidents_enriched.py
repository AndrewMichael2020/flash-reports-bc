"""add citizen fields to incidents_enriched

Revision ID: faa672a4c13f
Revises: d16f76e6ae3e
Create Date: 2025-12-08 06:10:32.771483

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'faa672a4c13f'
down_revision: Union[str, None] = 'd16f76e6ae3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new citizen-facing fields to incidents_enriched
    op.add_column('incidents_enriched', sa.Column('crime_category', sa.Text(), nullable=False, server_default='Unknown'))
    op.add_column('incidents_enriched', sa.Column('temporal_context', sa.Text(), nullable=True))
    op.add_column('incidents_enriched', sa.Column('weapon_involved', sa.Text(), nullable=True))
    op.add_column('incidents_enriched', sa.Column('tactical_advice', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove the citizen-facing fields
    op.drop_column('incidents_enriched', 'tactical_advice')
    op.drop_column('incidents_enriched', 'weapon_involved')
    op.drop_column('incidents_enriched', 'temporal_context')
    op.drop_column('incidents_enriched', 'crime_category')
