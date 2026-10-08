from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MetricId = Literal[
    "retail_index",
    "monthly_change",
    "yearly_change",
    "retail_volatility",
    "retail_anomaly_score",
    "country_comparison",
    "category_comparison",
]


class Metric(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: MetricId
    name: str
    description: str
    calculation: str
    source_tables: list[str]
    date_field: str
    included_statuses: list[str] = Field(default_factory=list)
    excluded_statuses: list[str] = Field(default_factory=list)
    currency: str | None = None
    aliases: list[str] = Field(default_factory=list)


RETAIL_METRICS = {
    metric.id: metric
    for metric in [
        Metric(
            id="retail_index",
            name="Retail volume index",
            description="Seasonally and calendar-adjusted retail sales volume; 2021 average equals 100.",
            calculation="retail_observations.value for the requested geography, category and period",
            source_tables=["retail_observations"],
            date_field="retail_observations.period",
            aliases=["index", "retail performance", "retail volume"],
        ),
        Metric(
            id="monthly_change",
            name="Monthly change",
            description="Difference from the immediately preceding available calendar month, in index points.",
            calculation="retail_observations.monthly_change",
            source_tables=["retail_observations"],
            date_field="retail_observations.period",
            aliases=["month over month", "monthly movement", "mom"],
        ),
        Metric(
            id="yearly_change",
            name="Annual change",
            description="Difference from the same calendar month one year earlier, in index points.",
            calculation="retail_observations.yearly_change",
            source_tables=["retail_observations"],
            date_field="retail_observations.period",
            aliases=["year over year", "annual movement", "yoy"],
        ),
        Metric(
            id="retail_volatility",
            name="Rolling volatility",
            description="Population standard deviation of up to 12 preceding monthly index-point changes.",
            calculation="retail_observations.rolling_volatility",
            source_tables=["retail_observations"],
            date_field="retail_observations.period",
            aliases=["volatility", "stability", "variation"],
        ),
        Metric(
            id="retail_anomaly_score",
            name="Anomaly score",
            description="Robust score for a monthly change relative to up to 36 preceding changes.",
            calculation="retail_observations.anomaly_score; is_anomaly is true when ABS(anomaly_score) >= 3.5",
            source_tables=["retail_observations"],
            date_field="retail_observations.period",
            aliases=["anomaly", "unusual movement", "outlier"],
        ),
        Metric(
            id="country_comparison",
            name="Country comparison",
            description="Retail index or derived change compared across EU member states.",
            calculation="Compare a consistent retail_observations measure and period grouped by geography",
            source_tables=["retail_observations"],
            date_field="retail_observations.period",
            aliases=["country ranking", "market comparison"],
        ),
        Metric(
            id="category_comparison",
            name="Category comparison",
            description="Retail index or derived change compared across the four curated retail categories.",
            calculation="Compare a consistent retail_observations measure and period grouped by category",
            source_tables=["retail_observations"],
            date_field="retail_observations.period",
            aliases=["category ranking", "retail segment comparison"],
        ),
    ]
}
