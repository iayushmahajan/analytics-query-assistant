from typing import Literal

from pydantic import BaseModel, ConfigDict

MetricId = Literal["revenue", "completed_revenue", "order_count", "completed_orders", "average_order_value", "customer_count", "product_sales", "category_sales", "country_sales"]
CURRENCY = "EUR"


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


def metric(id: MetricId, name: str, calculation: str, tables: list[str], *, completed=True, money=True, date="orders.order_date", aliases=None) -> Metric:
    return Metric(id=id, name=name, description=f"{name} across the selected date range and dimensions.",
                  calculation=calculation, source_tables=tables, date_field=date,
                  included_statuses=["completed"] if completed else ["pending", "completed", "cancelled"],
                  excluded_statuses=["pending", "cancelled"] if completed else [],
                  currency=CURRENCY if money else None, aliases=aliases or [])


METRICS = {m.id: m for m in [
    metric("revenue", "Revenue", "SUM(orders.total_amount) WHERE orders.status = 'completed'; never sum order totals after a line-item join", ["orders"], aliases=["sales", "sales revenue"]),
    metric("completed_revenue", "Completed revenue", "SUM(orders.total_amount) WHERE orders.status = 'completed'", ["orders"]),
    metric("order_count", "Order count", "COUNT(DISTINCT orders.id), all statuses unless explicitly filtered", ["orders"], completed=False, money=False, aliases=["orders"]),
    metric("completed_orders", "Completed orders", "COUNT(DISTINCT orders.id) WHERE orders.status = 'completed'", ["orders"], money=False),
    metric("average_order_value", "Average order value", "SUM(orders.total_amount) / NULLIF(COUNT(DISTINCT orders.id), 0) on completed orders at order grain", ["orders"], aliases=["AOV"]),
    metric("customer_count", "Customer count", "COUNT(DISTINCT customers.id); all registered customers unless explicitly filtered", ["customers"], completed=False, money=False, date="customers.created_at"),
    metric("product_sales", "Product sales", "SUM(order_items.quantity * order_items.unit_price) joined to completed orders, grouped by product; quantity means SUM(order_items.quantity)", ["orders", "order_items", "products"]),
    metric("category_sales", "Category sales", "SUM(order_items.quantity * order_items.unit_price) joined to completed orders, grouped by category", ["orders", "order_items", "products", "categories"]),
    metric("country_sales", "Country / region sales", "SUM(orders.total_amount) on completed orders joined to customers and countries, grouped by country or region", ["orders", "customers", "countries"]),
]}

# Registered customers have no order-status restriction.
METRICS["customer_count"] = METRICS["customer_count"].model_copy(update={"included_statuses": [], "excluded_statuses": []})
