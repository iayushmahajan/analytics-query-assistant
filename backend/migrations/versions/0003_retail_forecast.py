"""Separate public retail transactions and evaluated demand forecasts."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "retail_lines",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("invoice_no", sa.String(20), nullable=False),
        sa.Column("stock_code", sa.String(30), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("invoice_date", sa.DateTime, nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("is_sale", sa.Boolean, nullable=False),
    )
    op.create_index("ix_retail_lines_date", "retail_lines", ["invoice_date"])
    op.create_index("ix_retail_lines_product_date", "retail_lines", ["stock_code", "invoice_date"])
    op.create_index("ix_retail_lines_invoice", "retail_lines", ["invoice_no"])
    op.create_table(
        "retail_forecasts",
        sa.Column("stock_code", sa.String(30), primary_key=True),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("forecast_week", sa.Date, nullable=False),
        sa.Column("predicted_units", sa.Numeric(12, 1), nullable=False),
        sa.Column("baseline_units", sa.Numeric(12, 1), nullable=False),
        sa.Column("model_mae", sa.Numeric(12, 2), nullable=False),
        sa.Column("baseline_mae", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.String(40), nullable=False),
        sa.Column("history", sa.JSON, nullable=False),
        sa.Column("backtest", sa.JSON, nullable=False),
    )


def downgrade():
    op.drop_table("retail_forecasts")
    op.drop_table("retail_lines")
