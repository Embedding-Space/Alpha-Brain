"""Initial schema

Revision ID: fdb499244a88
Revises: 
Create Date: 2025-07-23 20:55:13.839997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fdb499244a88'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # This is our baseline migration. All existing tables are already
    # in the database from before we added Alembic, so we don't need
    # to create them here. This migration serves as the starting point
    # for future schema changes.
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # Nothing to downgrade in the baseline
    pass
