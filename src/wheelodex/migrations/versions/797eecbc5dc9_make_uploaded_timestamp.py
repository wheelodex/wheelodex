"""Make uploaded timestamp

Revision ID: 797eecbc5dc9
Revises: b3dbe476e055
Create Date: 2019-10-29 22:31:51.573165+00:00

"""
import re
from   alembic import op
import pyrfc3339
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '797eecbc5dc9'
down_revision = 'b3dbe476e055'
branch_labels = None
depends_on = None

wheels = sa.Table(
    'wheels', sa.MetaData(),
    sa.Column('id', sa.Integer, primary_key=True, nullable=False),
    sa.Column('filename', sa.Unicode(2048), nullable=False, unique=True),
    sa.Column('url', sa.Unicode(2048), nullable=False),
    sa.Column(
        'version_id',
        sa.Integer,
        sa.ForeignKey('versions.id', ondelete='CASCADE'),
        nullable=False,
    ),
    sa.Column('size', sa.Integer, nullable=False),
    sa.Column('md5', sa.Unicode(32), nullable=True),
    sa.Column('sha256', sa.Unicode(64), nullable=True),
    sa.Column('uploaded', sa.Unicode(32), nullable=False),
    sa.Column('uploaded_ts', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ordering', sa.Integer, nullable=False, default=0),
)

def upgrade():
    op.add_column(
        'wheels',
        sa.Column('uploaded_ts', sa.DateTime(timezone=True), nullable=True),
    )
    conn = op.get_bind()
    for wid, uploaded_str in conn.execute(
        sa.select([wheels.c.id, wheels.c.uploaded])
    ):
        uploaded_ts = parse_timestamp(uploaded_str)
        conn.execute(
            wheels.update().values(uploaded_ts=uploaded_ts)
                           .where(wheels.c.id == wid)
        )
    op.drop_column('wheels', 'uploaded')
    op.alter_column(
        'wheels',
        'uploaded_ts',
        new_column_name='uploaded',
        nullable=False,
    )

def downgrade():
    op.add_column(
        'wheels',
        sa.Column('uploaded_str', sa.Unicode(32), nullable=True),
    )
    conn = op.get_bind()
    for wid, uploaded_ts in conn.execute(
        sa.select([wheels.c.id, wheels.c.uploaded])
    ):
        uploaded_str = uploaded_ts.isoformat()
        conn.execute(
            wheels.update().values(uploaded_str=uploaded_str)
                           .where(wheels.c.id == wid)
        )
    op.drop_column('wheels', 'uploaded')
    op.alter_column(
        'wheels',
        'uploaded_str',
        new_column_name='uploaded',
        nullable=False,
    )

# Importing this from ..util doesn't work for some reason
def parse_timestamp(s):
    """ Parse an ISO 8601 timestamp, assuming anything naïve is in UTC """
    if re.fullmatch(r'\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(\.\d+)?', s):
        s += 'Z'
    return pyrfc3339.parse(s)
