"""store meal photo key and which storage holds it (local or s3)

Revision ID: b7d41c2e9f10
Revises: 3e8020d46bfa
Create Date: 2026-10-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d41c2e9f10'
down_revision: Union[str, None] = '3e8020d46bfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # image_path held a local file name; it now holds an S3 object key or a file name.
    op.alter_column('meals', 'image_path', new_column_name='image_key')
    op.add_column('meals', sa.Column('image_storage', sa.String(length=10), nullable=True))
    # Every photo saved so far is on local disk.
    op.execute("UPDATE meals SET image_storage = 'local' WHERE image_key IS NOT NULL")


def downgrade() -> None:
    op.drop_column('meals', 'image_storage')
    op.alter_column('meals', 'image_key', new_column_name='image_path')
