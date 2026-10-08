"""Replace historical SKU forecasts with a current German retail index forecast."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.drop_table("retail_forecasts")
    op.create_table(
        "market_observations",
        sa.Column("period", sa.Date, primary_key=True),
        sa.Column("value", sa.Numeric(10, 3), nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
    )
    op.create_table(
        "market_imports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_count", sa.Integer, nullable=False),
        sa.Column("missing_periods", sa.Integer, nullable=False),
        sa.Column("latest_period", sa.Date, nullable=False),
        sa.Column("latest_status", sa.String(20), nullable=True),
    )
    op.create_table(
        "market_forecasts",
        sa.Column("geo_code", sa.String(10), primary_key=True),
        sa.Column("target_period", sa.Date, nullable=False),
        sa.Column("training_cutoff", sa.Date, nullable=False),
        sa.Column("predicted_index", sa.Numeric(10, 3), nullable=False),
        sa.Column("prediction_lower", sa.Numeric(10, 3), nullable=False),
        sa.Column("prediction_upper", sa.Numeric(10, 3), nullable=False),
        sa.Column("baseline_index", sa.Numeric(10, 3), nullable=False),
        sa.Column("method", sa.String(40), nullable=False),
        sa.Column("baseline_method", sa.String(40), nullable=False),
        sa.Column("validation_mae", sa.Numeric(10, 3), nullable=False),
        sa.Column("baseline_validation_mae", sa.Numeric(10, 3), nullable=False),
        sa.Column("test_mae", sa.Numeric(10, 3), nullable=False),
        sa.Column("baseline_test_mae", sa.Numeric(10, 3), nullable=False),
        sa.Column("test_wape", sa.Numeric(8, 5), nullable=False),
        sa.Column("test_bias", sa.Numeric(10, 3), nullable=False),
        sa.Column("interval_coverage", sa.Numeric(8, 5), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("validation_months", sa.Integer, nullable=False),
        sa.Column("test_months", sa.Integer, nullable=False),
        sa.Column("latest_observation_status", sa.String(20), nullable=True),
        sa.Column("history", sa.JSON, nullable=False),
        sa.Column("backtest", sa.JSON, nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    raise RuntimeError("The retired SKU forecast results cannot be reconstructed by downgrade")
