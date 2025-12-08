"""add incident_occurred_at to incidents_enriched

Revision ID: abcd1234
Revises: 0c0db8feb7cb
Create Date: 2025-12-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "abcd1234"
down_revision: Union[str, None] = "0c0db8feb7cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents_enriched",
        sa.Column("incident_occurred_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents_enriched", "incident_occurred_at")
