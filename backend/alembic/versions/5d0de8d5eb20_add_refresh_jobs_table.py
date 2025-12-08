"""add_refresh_jobs_table

Revision ID: 5d0de8d5eb20
Revises: 6d4386b3f6ab
Create Date: 2025-12-08 11:42:43.584306

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d0de8d5eb20'
down_revision: Union[str, None] = '6d4386b3f6ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create refresh_jobs table
    op.create_table('refresh_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('region', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('new_articles', sa.Integer(), nullable=True),
        sa.Column('total_incidents', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_jobs_id'), 'refresh_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_refresh_jobs_job_id'), 'refresh_jobs', ['job_id'], unique=True)


def downgrade() -> None:
    # Drop refresh_jobs table
    op.drop_index(op.f('ix_refresh_jobs_job_id'), table_name='refresh_jobs')
    op.drop_index(op.f('ix_refresh_jobs_id'), table_name='refresh_jobs')
    op.drop_table('refresh_jobs')
