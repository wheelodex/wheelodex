"""
Add EntryPointGroup.summary

Revision ID: 2508919c9f86
Revises:
Create Date: 2018-10-08 22:38:52.231851+00:00
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "2508919c9f86"
down_revision: None = None
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "entry_point_groups",
        sa.Column("summary", sa.Unicode(length=2048), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("entry_point_groups", "summary")
    # ### end Alembic commands ###