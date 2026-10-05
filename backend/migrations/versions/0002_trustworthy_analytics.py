"""Bounded response snapshots and business data constraints."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = depends_on = None
CONSTRAINTS = [
    ("orders", "ck_order_status", "status IN ('pending', 'completed', 'cancelled')"),
    ("orders", "ck_order_amount", "total_amount >= 0"),
    ("order_items", "ck_item_quantity", "quantity > 0"),
    ("order_items", "ck_item_price", "unit_price >= 0"),
    ("products", "ck_product_price", "price >= 0"),
]


def upgrade():
    op.add_column("query_history", sa.Column("snapshot", sa.JSON, nullable=True))
    for table, name, expression in CONSTRAINTS:
        op.create_check_constraint(name, table, expression)


def downgrade():
    for table, name, _ in reversed(CONSTRAINTS):
        op.drop_constraint(name, table, type_="check")
    op.drop_column("query_history", "snapshot")
