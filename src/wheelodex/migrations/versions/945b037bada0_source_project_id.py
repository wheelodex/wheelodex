"""source_project_id

Revision ID: 945b037bada0
Revises: dac430582787
Create Date: 2020-03-19 16:47:48.953548+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '945b037bada0'
down_revision = 'dac430582787'
branch_labels = None
depends_on = None

schema = sa.MetaData()

project = sa.Table(
    'projects', schema,
    sa.Column('id', sa.Integer, primary_key=True, nullable=False),
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

wheel_data = sa.Table(
    'wheel_data', schema,
    sa.Column('id', sa.Integer, primary_key=True, nullable=False),
    sa.Column(
        'wheel_id',
        sa.Integer,
        sa.ForeignKey('wheels.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    ),
)

dependency_rel = sa.Table(
    'dependency_tbl', schema,
    sa.Column(
        'wheel_data_id',
        sa.Integer,
        sa.ForeignKey('wheel_data.id', ondelete='CASCADE'),
        nullable=False,
        primary_key=True,
    ),
    sa.Column(
        'project_id',
        sa.Integer,
        sa.ForeignKey('projects.id', ondelete='RESTRICT'),
        nullable=False,
        primary_key=True,
    ),
    sa.Column(
        'source_project_id',
        sa.Integer,
        sa.ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
    ),
)

def upgrade():
    op.add_column(
        'dependency_tbl',
        sa.Column('source_project_id', sa.Integer(), nullable=True)
    )
    op.drop_constraint(
        'dependency_tbl_wheel_data_id_project_id_key',
        'dependency_tbl',
        type_='unique'
    )
    op.create_foreign_key(
        None,
        'dependency_tbl',
        'projects',
        ['source_project_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_primary_key(
        'dependency_tbl_wheel_data_id_project_id_primary_key',
        'dependency_tbl',
        ['wheel_data_id', 'project_id'],
    )
    conn = op.get_bind()

    """
    for pid, wdid in conn.execute(
        sa.select([project.c.id, wheel_data.c.id])
          .select_from(project.join(version).join(wheel).join(wheel_data))
    ):
        conn.execute(
            dependency_rel.update().values(source_project_id=pid)
                          .where(dependency_rel.c.wheel_data_id == wdid)
        )
    """

    conn.execute(
        dependency_rel.update().values(source_project_id=project.c.id)
                      .where(dependency_rel.c.wheel_data_id == wheel_data.c.id)
                      .where(wheel_data.c.wheel_id == wheel.c.id)
                      .where(wheel.c.version_id == version.c.id)
                      .where(version.c.project_id == project.c.id)
    )

    op.alter_column('dependency_tbl', 'source_project_id', nullable=False)

def downgrade():
    op.drop_constraint(
        'dependency_tbl_wheel_data_id_project_id_primary_key',
        'dependency_tbl',
        type_='primary',
    )
    op.drop_constraint(None, 'dependency_tbl', type_='foreignkey')
    op.create_unique_constraint(
        'dependency_tbl_wheel_data_id_project_id_key',
        'dependency_tbl',
        ['wheel_data_id', 'project_id']
    )
    op.drop_column('dependency_tbl', 'source_project_id')
