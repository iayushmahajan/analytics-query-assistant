"""Add import provenance and independent forecast evaluation fields."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "retail_imports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("archive_bytes", sa.Integer, nullable=False),
        sa.Column("imported_lines", sa.Integer, nullable=False),
        sa.Column("dropped_lines", sa.Integer, nullable=False),
    )
    for name, column_type in (
        ("training_cutoff", sa.Date()),
        ("prediction_lower", sa.Numeric(12, 1)),
        ("prediction_upper", sa.Numeric(12, 1)),
        ("test_mae", sa.Numeric(12, 2)),
        ("baseline_test_mae", sa.Numeric(12, 2)),
        ("test_wape", sa.Numeric(8, 4)),
        ("test_bias", sa.Numeric(12, 2)),
        ("interval_coverage", sa.Numeric(8, 4)),
        ("validation_weeks", sa.Integer()),
        ("test_weeks", sa.Integer()),
        ("confidence", sa.String(20)),
    ):
        op.add_column("retail_forecasts", sa.Column(name, column_type, nullable=True))


def downgrade():
    for name in (
        "confidence",
        "test_weeks",
        "validation_weeks",
        "interval_coverage",
        "test_bias",
        "test_wape",
        "baseline_test_mae",
        "test_mae",
        "prediction_upper",
        "prediction_lower",
        "training_cutoff",
    ):
        op.drop_column("retail_forecasts", name)
    op.drop_table("retail_imports")
