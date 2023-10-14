"""
Rename wheelodex_version

Revision ID: 8820a6b34f40
Revises: b835c6894d5a
Create Date: 2018-10-12 20:33:03.002855+00:00
"""

from __future__ import annotations
from alembic import op

# revision identifiers, used by Alembic.
revision = "8820a6b34f40"
down_revision = "b835c6894d5a"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.alter_column(
        "wheel_data",
        "wheelodex_version",
        new_column_name="wheel_inspect_version",
    )


def downgrade() -> None:
    op.alter_column(
        "wheel_data",
        "wheel_inspect_version",
        new_column_name="wheelodex_version",
    )
