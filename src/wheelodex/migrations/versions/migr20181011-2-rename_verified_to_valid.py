"""
Rename "verified" to "valid"

Revision ID: b835c6894d5a
Revises: aec0bfd26f9a
Create Date: 2018-10-11 20:19:13.081503+00:00
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b835c6894d5a"
down_revision = "aec0bfd26f9a"
branch_labels: None = None
depends_on: None = None

wheel_data = sa.Table(
    "wheel_data",
    sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True, nullable=False),
    sa.Column(
        "wheel_id",
        sa.Integer,
        sa.ForeignKey("wheels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    sa.Column("raw_data", sa.JSON, nullable=False),
    sa.Column("processed", sa.DateTime(timezone=True), nullable=False),
    sa.Column("wheelodex_version", sa.Unicode(32), nullable=False),
    sa.Column("summary", sa.Unicode(2048), nullable=True),
    sa.Column("valid", sa.Boolean, nullable=False),
)


def upgrade() -> None:
    op.alter_column("wheel_data", "verified", new_column_name="valid")
    conn = op.get_bind()
    for wdid, data in conn.execute(sa.select(wheel_data.c.id, wheel_data.c.raw_data)):
        data["valid"] = data.pop("verifies")
        if "verify_error" in data:
            data["validation_error"] = data.pop("verify_error")
        conn.execute(
            wheel_data.update().values(raw_data=data).where(wheel_data.c.id == wdid)
        )


def downgrade() -> None:
    conn = op.get_bind()
    for wdid, data in conn.execute(sa.select(wheel_data.c.id, wheel_data.c.raw_data)):
        data["verifies"] = data.pop("valid")
        if "validation_error" in data:
            data["verify_error"] = data.pop("validation_error")
        conn.execute(
            wheel_data.update().values(raw_data=data).where(wheel_data.c.id == wdid)
        )
    op.alter_column("wheel_data", "valid", new_column_name="verified")
