"""Add Project.has_wheels

Revision ID: a9bd6c2d6b32
Revises: b37f849a527d
Create Date: 2020-04-03 19:55:05.312729+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9bd6c2d6b32'
down_revision = 'b37f849a527d'
branch_labels = None
depends_on = None

schema = sa.MetaData()

project = sa.Table(
    'projects', schema,
    sa.Column('id', sa.Integer, primary_key=True, nullable=False),
    sa.Column('has_wheels', sa.Boolean(), nullable=False),
)

version = sa.Table(
    'versions', schema,
    sa.Column('id', sa.Integer, primary_key=True, nullable=False),
    sa.Column(
        'project_id',
        sa.Integer,
        sa.ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
    ),
)

wheel = sa.Table(
    'wheels', schema,
    sa.Column('id', sa.Integer, primary_key=True, nullable=False),
    sa.Column(
        'version_id',
        sa.Integer,
        sa.ForeignKey('versions.id', ondelete='CASCADE'),
        nullable=False,
    ),
)

def upgrade():
    op.add_column('projects', sa.Column('has_wheels', sa.Boolean(), nullable=True))
    conn = op.get_bind()
    conn.execute(project.update().values(has_wheels=False))
    conn.execute(
        project.update().values(has_wheels=True)
               .where(project.c.id == version.c.project_id)
               .where(version.c.id == wheel.c.version_id)
    )
    op.alter_column('projects', 'has_wheels', nullable=False)

def downgrade():
    op.drop_column('projects', 'has_wheels')
