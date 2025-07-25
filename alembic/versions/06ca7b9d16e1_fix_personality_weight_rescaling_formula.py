"""Fix personality weight rescaling formula

Revision ID: 06ca7b9d16e1
Revises: 82a2ea345f7a
Create Date: 2025-07-25 09:32:07.251108

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06ca7b9d16e1'
down_revision: Union[str, Sequence[str], None] = '82a2ea345f7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fix the incorrect rescaling from previous migration
    # Previous migration used: new = (old / 5.0) - 1.0
    # To reverse: old = (new + 1.0) * 5.0
    # Then apply correct formula: new = (old * 2.0) - 1.0
    # Combined: new = ((current + 1.0) * 5.0 * 2.0) - 1.0 = (current + 1.0) * 10.0 - 1.0
    op.execute("""
        UPDATE personality_directives 
        SET weight = ((weight + 1.0) * 10.0) - 1.0
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Reverse the fix to go back to the incorrectly scaled values
    # Reverse of: new = ((old + 1.0) * 10.0) - 1.0
    # old = ((new + 1.0) / 10.0) - 1.0
    op.execute("""
        UPDATE personality_directives 
        SET weight = ((weight + 1.0) / 10.0) - 1.0
    """)
