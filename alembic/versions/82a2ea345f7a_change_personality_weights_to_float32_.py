"""Change personality weights to float32 with -1 to 1 range

Revision ID: 82a2ea345f7a
Revises: cad220075505
Create Date: 2025-07-25 09:24:37.500310

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82a2ea345f7a'
down_revision: Union[str, Sequence[str], None] = 'cad220075505'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # First, rescale existing weights from 0-10 to -1 to 1
    # Formula: new_weight = (old_weight / 5.0) - 1.0
    # This maps: 0->-1, 5->0, 10->1
    op.execute("""
        UPDATE personality_directives 
        SET weight = (weight / 5.0) - 1.0
    """)
    
    # Then change the column type from DECIMAL to REAL (float32)
    op.alter_column('personality_directives', 'weight',
                    existing_type=sa.DECIMAL(precision=3, scale=2),
                    type_=sa.REAL(),
                    existing_nullable=False)
    
    # Add check constraint for new range (no existing constraint to drop)
    op.create_check_constraint(
        'weight_range',
        'personality_directives',
        'weight >= -1.0 AND weight <= 1.0'
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the check constraint
    op.drop_constraint('weight_range', 'personality_directives')
    
    # Rescale weights back from -1 to 1 to 0-10
    # Formula: old_weight = (new_weight + 1.0) * 5.0
    op.execute("""
        UPDATE personality_directives 
        SET weight = (weight + 1.0) * 5.0
    """)
    
    # Change column type back to DECIMAL
    op.alter_column('personality_directives', 'weight',
                    existing_type=sa.REAL(),
                    type_=sa.DECIMAL(precision=3, scale=2),
                    existing_nullable=False)
