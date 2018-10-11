"""Rename "verified" to "valid"

Revision ID: b835c6894d5a
Revises: aec0bfd26f9a
Create Date: 2018-10-11 20:19:13.081503+00:00

"""
from   alembic import op
import sqlalchemy as S
from   sqlalchemy_utils import JSONType


# revision identifiers, used by Alembic.
revision = 'b835c6894d5a'
down_revision = 'aec0bfd26f9a'
branch_labels = None
depends_on = None

wheel_data = S.Table(
    'wheel_data', S.MetaData(),
    S.Column('id', S.Integer, primary_key=True, nullable=False),
    S.Column(
        'wheel_id',
        S.Integer,
        S.ForeignKey('wheels.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    ),
    S.Column('raw_data', JSONType, nullable=False),
    S.Column('processed', S.DateTime(timezone=True), nullable=False),
    S.Column('wheelodex_version', S.Unicode(32), nullable=False),
    S.Column('summary', S.Unicode(2048), nullable=True),
    S.Column('valid', S.Boolean, nullable=False),
)

def upgrade():
    op.alter_column('wheel_data', 'verified', new_column_name='valid')
    conn = op.get_bind()
    for wdid, data in conn.execute(S.select([
        wheel_data.c.id,
        wheel_data.c.raw_data,
    ])):
        data["valid"] = data.pop("verifies")
        if "verify_error" in data:
            data["validation_error"] = data.pop("verify_error")
        conn.execute(
            wheel_data.update().values(raw_data=data)
                               .where(wheel_data.c.id == wdid)
        )

def downgrade():
    conn = op.get_bind()
    for wdid, data in conn.execute(S.select([
        wheel_data.c.id,
        wheel_data.c.raw_data,
    ])):
        data["verifies"] = data.pop("valid")
        if "validation_error" in data:
            data["verify_error"] = data.pop("validation_error")
        conn.execute(
            wheel_data.update().values(raw_data=data)
                               .where(wheel_data.c.id == wdid)
        )
    op.alter_column('wheel_data', 'valid', new_column_name='verified')
