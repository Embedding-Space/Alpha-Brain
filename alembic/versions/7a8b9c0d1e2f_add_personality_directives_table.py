"""Add personality_directives table

Revision ID: 7a8b9c0d1e2f
Revises: cad220075505
Create Date: 2025-07-25 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, None] = 'cad220075505'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create personality_directives table
    op.create_table('personality_directives',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('directive', sa.Text(), nullable=False),
        sa.Column('weight', sa.DECIMAL(precision=3, scale=2), nullable=False),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_personality_directives_category'), 'personality_directives', ['category'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_personality_directives_category'), table_name='personality_directives')
    op.drop_table('personality_directives')