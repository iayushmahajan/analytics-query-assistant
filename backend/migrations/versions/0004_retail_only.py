"""Remove the retired synthetic sales workspace and its saved analyses."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = depends_on = None


def upgrade():
    op.execute(sa.text("DELETE FROM query_history WHERE snapshot ->> 'dataset' IS DISTINCT FROM 'retail'"))
    for table in ("order_items", "orders", "products", "customers", "categories", "countries"):
        op.drop_table(table)


def downgrade():
    raise RuntimeError("The removed synthetic records cannot be restored by a schema downgrade.")
