"""Original schema. Existing original installations may stamp this revision after backup."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "countries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("country_id", sa.Integer, sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_customers_email", "customers", ["email"], unique=True)
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("order_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
    )
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
    )
    op.create_table(
        "query_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("generated_sql", sa.Text, nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("row_count", sa.Integer),
        sa.Column("execution_time_ms", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    for table, columns in {
        "countries": ["id"],
        "categories": ["id"],
        "customers": ["id"],
        "products": ["id", "name"],
        "orders": ["id", "customer_id", "order_date", "status"],
        "order_items": ["id", "order_id", "product_id"],
        "query_history": ["id", "status"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in [
        "query_history",
        "order_items",
        "orders",
        "products",
        "customers",
        "categories",
        "countries",
    ]:
        op.drop_table(table)
