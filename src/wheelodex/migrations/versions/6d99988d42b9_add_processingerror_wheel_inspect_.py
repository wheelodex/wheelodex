"""Add ProcessingError.wheel_inspect_version

Revision ID: 6d99988d42b9
Revises: 797eecbc5dc9
Create Date: 2019-11-01 22:39:50.050487+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d99988d42b9'
down_revision = '797eecbc5dc9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'processing_errors',
        sa.Column(
            'wheel_inspect_version',
            sa.Unicode(length=32),
            nullable=True,
        ),
    )

def downgrade():
    op.drop_column('processing_errors', 'wheel_inspect_version')
