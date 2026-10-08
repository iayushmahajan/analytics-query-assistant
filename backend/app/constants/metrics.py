from typing import Literal

from pydantic import BaseModel, ConfigDict

MetricId = Literal[
    "retail_gross_sales",
    "retail_units",
    "retail_invoices",
    "retail_product_sales",
    "retail_country_sales",
]


class Metric(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: MetricId
    name: str
    description: str
    calculation: str
    source_tables: list[str]
    date_field: str
    included_statuses: list[str]
    excluded_statuses: list[str]
    currency: str | None = None
    aliases: list[str] = []


# Positive, priced, non-cancelled invoice lines are gross sales.
# The source does not establish net revenue or refunds.
RETAIL_METRICS = {
    m.id: m
    for m in [
        Metric(id="retail_gross_sales", name="Gross sales", description="Positive priced, non-cancelled invoice lines.", calculation="SUM(retail_lines.quantity * retail_lines.unit_price) on sale lines only", source_tables=["retail_lines"], date_field="retail_lines.invoice_date", included_statuses=["sale"], excluded_statuses=["cancellation", "non-sale"], currency="GBP", aliases=["sales", "sales value"]),
        Metric(id="retail_units", name="Units sold", description="Units on sale lines.", calculation="SUM(retail_lines.quantity) on sale lines only", source_tables=["retail_lines"], date_field="retail_lines.invoice_date", included_statuses=["sale"], excluded_statuses=["cancellation", "non-sale"], aliases=["quantity"]),
        Metric(id="retail_invoices", name="Sales invoices", description="Distinct invoices with sale lines.", calculation="COUNT(DISTINCT retail_lines.invoice_no) on sale lines only", source_tables=["retail_lines"], date_field="retail_lines.invoice_date", included_statuses=["sale"], excluded_statuses=["cancellation", "non-sale"], aliases=["orders"]),
        Metric(id="retail_product_sales", name="Product gross sales", description="Gross sales by stock code or description.", calculation="SUM(retail_lines.quantity * retail_lines.unit_price) grouped by stock_code or description on sale lines only", source_tables=["retail_lines"], date_field="retail_lines.invoice_date", included_statuses=["sale"], excluded_statuses=["cancellation", "non-sale"], currency="GBP", aliases=["product sales"]),
        Metric(id="retail_country_sales", name="Country gross sales", description="Gross sales by invoice country.", calculation="SUM(retail_lines.quantity * retail_lines.unit_price) grouped by country on sale lines only", source_tables=["retail_lines"], date_field="retail_lines.invoice_date", included_statuses=["sale"], excluded_statuses=["cancellation", "non-sale"], currency="GBP", aliases=["country sales"]),
    ]
}
