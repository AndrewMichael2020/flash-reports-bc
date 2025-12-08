"""add incident_occurred_at to incidents_enriched

Revision ID: 6d4386b3f6ab
Revises: abcd1234
Create Date: 2025-12-08 08:01:34.392768

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d4386b3f6ab'
down_revision: Union[str, None] = 'abcd1234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
