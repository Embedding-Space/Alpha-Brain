"""Add name_index table

Revision ID: 29f34d901ee8
Revises: fdb499244a88
Create Date: 2025-07-23 20:56:05.411750

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29f34d901ee8'
down_revision: Union[str, Sequence[str], None] = 'fdb499244a88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create name_index table for entity canonicalization
    op.create_table(
        'name_index',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('canonical_name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_name_index_name'), 'name_index', ['name'], unique=True)
    op.create_index(op.f('ix_name_index_canonical_name'), 'name_index', ['canonical_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('ix_name_index_canonical_name'), table_name='name_index')
    op.drop_index(op.f('ix_name_index_name'), table_name='name_index')
    
    # Drop table
    op.drop_table('name_index')
