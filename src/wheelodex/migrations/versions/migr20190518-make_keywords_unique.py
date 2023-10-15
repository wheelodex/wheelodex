"""
Make keywords unique

Revision ID: b3dbe476e055
Revises: f43499b4f914
Create Date: 2019-05-18 23:07:29.744512+00:00
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b3dbe476e055"
down_revision = "f43499b4f914"
branch_labels: None = None
depends_on: None = None

keywords = sa.Table(
    "keywords",
    sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True, nullable=False),
    sa.Column(
        "wheel_data_id",
        sa.Integer,
        # sa.ForeignKey('wheel_data.id', ondelete='CASCADE'),
        nullable=False,
    ),
    sa.Column("name", sa.Unicode(2048), nullable=False),
)


def upgrade() -> None:
    """
    DELETE FROM keywords a USING (
        SELECT MIN(id) as id, wheel_data_id, name
        FROM keywords
        GROUP BY wheel_data_id, name
        HAVING COUNT(*) > 1
    ) b
    WHERE a.wheel_data_id = b.wheel_data_id
      AND a.name = b.name
      AND a.id <> b.id
    """

    conn = op.get_bind()
    subq = (
        sa.select(
            sa.func.MIN(keywords.c.id).label("id"),
            keywords.c.wheel_data_id,
            keywords.c.name,
        )
        .group_by(keywords.c.wheel_data_id, keywords.c.name)
        .having(sa.func.count() > 1)
        .alias()
    )
    conn.execute(
        keywords.delete()
        .where(keywords.c.wheel_data_id == subq.c.wheel_data_id)
        .where(keywords.c.name == subq.c.name)
        .where(keywords.c.id != subq.c.id)
    )
    op.create_unique_constraint(
        "keywords_wheel_data_id_name_key", "keywords", ["wheel_data_id", "name"]
    )


def downgrade() -> None:
    op.drop_constraint("keywords_wheel_data_id_name_key", "keywords", type_="unique")
