"""Drop unused entities table

Revision ID: cad220075505
Revises: 29f34d901ee8
Create Date: 2025-07-23 15:09:26.596125

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cad220075505'
down_revision: Union[str, Sequence[str], None] = '29f34d901ee8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old entities table since we've moved to name_index
    # Use IF EXISTS to handle cases where table was never created (fresh installs)
    op.execute('DROP TABLE IF EXISTS entities')


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate the entities table if we need to rollback
    op.create_table(
        'entities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('canonical_name', sa.String(), nullable=False),
        sa.Column('aliases', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('entity_type', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Recreate the indexes that were on the original table
    op.create_index(op.f('ix_entities_canonical_name'), 'entities', ['canonical_name'], unique=False)
    op.create_index('ix_entities_aliases', 'entities', ['aliases'], unique=False, postgresql_using='gin')
