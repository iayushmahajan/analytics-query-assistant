"""Consolidate analytics around one multidimensional Eurostat retail dataset."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = depends_on = None


def upgrade():
    op.execute(sa.text("DELETE FROM query_history"))
    for table in (
        "market_forecasts",
        "market_observations",
        "market_imports",
        "retail_lines",
        "retail_imports",
    ):
        op.drop_table(table)

    op.create_table(
        "retail_observations",
        sa.Column("geo_code", sa.String(12), primary_key=True),
        sa.Column("geography", sa.String(100), nullable=False),
        sa.Column("category_code", sa.String(30), primary_key=True),
        sa.Column("category", sa.String(200), nullable=False),
        sa.Column("period", sa.Date, primary_key=True),
        sa.Column("value", sa.Numeric(10, 3), nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("monthly_change", sa.Numeric(10, 3), nullable=True),
        sa.Column("yearly_change", sa.Numeric(10, 3), nullable=True),
        sa.Column("rolling_volatility", sa.Numeric(10, 3), nullable=True),
        sa.Column("anomaly_score", sa.Numeric(10, 3), nullable=True),
        sa.Column("is_anomaly", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint("value > 0", name="ck_retail_observation_value"),
    )
    op.create_index("ix_retail_observations_period", "retail_observations", ["period"])
    op.create_index(
        "ix_retail_observations_category_period",
        "retail_observations",
        ["category_code", "period"],
    )
    op.create_index(
        "ix_retail_observations_anomaly",
        "retail_observations",
        ["is_anomaly", "period"],
    )
    op.create_table(
        "retail_imports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_count", sa.Integer, nullable=False),
        sa.Column("missing_cells", sa.Integer, nullable=False),
        sa.Column("earliest_period", sa.Date, nullable=False),
        sa.Column("latest_period", sa.Date, nullable=False),
        sa.Column("geography_count", sa.Integer, nullable=False),
        sa.Column("category_count", sa.Integer, nullable=False),
    )


def downgrade():
    raise RuntimeError("Removed UCI and forecast records cannot be reconstructed by downgrade")
