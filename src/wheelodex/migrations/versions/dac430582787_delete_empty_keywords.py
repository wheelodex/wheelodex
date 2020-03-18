"""Delete empty keywords

Revision ID: dac430582787
Revises: 6d99988d42b9
Create Date: 2020-01-30 20:08:37.311976+00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'dac430582787'
down_revision = '6d99988d42b9'
branch_labels = None
depends_on = None

keywords = sa.Table(
    'keywords', sa.MetaData(),
    sa.Column('id', sa.Integer, primary_key=True, nullable=False),
    sa.Column('wheel_data_id', sa.Integer, nullable=False),
    sa.Column('name', sa.Unicode(2048), nullable=False),
    sa.UniqueConstraint('wheel_data_id', 'name'),
)

def sql_strip(col):
    # This produces `TRIM(col, chars)`, which works in PostgreSQL and SQLite
    # but not MySQL:
    return sa.func.trim(col, ' \t\n\r\x0B\f')
    # MySQL requires the SQL syntax `TRIM(chars FROM col)` (note the reversed
    # order of operands), which also works in PostgreSQL but not SQLite.  I
    # can't figure out how to express this in SQLALchemy without using
    # `text()`, and on top of that is the problem of ensuring that the correct
    # syntax is emitted for whichever database type is in use.

def upgrade():
    conn = op.get_bind()
    conn.execute(keywords.delete().where(sql_strip(keywords.c.name) == ''))
    conn.execute(keywords.update().values(name=sql_strip(keywords.c.name)))

def downgrade():
    pass
