import json
import re
from decimal import Decimal, InvalidOperation
from statistics import quantiles

from app.api.schemas.query import QueryPlan, ResultAnalysis
from app.constants.metrics import METRICS
from app.core.config import settings
from app.services.sql_validator import ValidatedSQL


def numeric(value) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    try:
        return Decimal(str(value)).is_finite()
    except InvalidOperation:
        return False


def build_result_context(result: dict, validated: ValidatedSQL) -> dict:
    # Results stay inside the application process; this bounds calculation cost.
    # The restricted database role remains the boundary for private columns.
    _ = validated
    indexes = list(range(len(result["columns"])))
    context = {
        "columns": [result["columns"][i] for i in indexes],
        "rows": [],
        "returned_row_count": result["row_count"],
        "possibly_truncated": result["possibly_truncated"],
        "sampled": False,
    }
    while len(json.dumps(context).encode()) > settings.ANALYSIS_MAX_BYTES and indexes:
        indexes.pop()
        context["columns"].pop()
    for row in result["rows"][: settings.ANALYSIS_MAX_ROWS]:
        context["rows"].append([row[i] for i in indexes])
        if len(json.dumps(context).encode()) > settings.ANALYSIS_MAX_BYTES:
            context["rows"].pop()
            break
    context["sampled"] = len(context["rows"]) < result["row_count"]
    return context


def _number(value) -> Decimal:
    return Decimal(str(value))


def _format_value(value: Decimal, currency: str | None) -> str:
    if currency:
        return f"{currency} {value:,.2f}"
    if value == value.to_integral_value():
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip()


def _measure_currency(currency: str | None, column: str) -> str | None:
    name = column.lower()
    non_currency = ("quantity", "units", "count", "orders", "customers")
    return None if any(token in name for token in non_currency) else currency


def _is_temporal(column: str, labels: list[str]) -> bool:
    if any(token in column.lower() for token in ("date", "month", "quarter", "year", "week", "day")):
        return True
    return bool(labels) and all(re.match(r"^\d{4}(?:-\d{2})?(?:-\d{2})?", label) for label in labels)


def _follow_ups(metric_id: str) -> list[str]:
    if metric_id in {"revenue", "completed_revenue"}:
        return [
            "Show monthly completed revenue for 2025.",
            "Break completed revenue down by country.",
            "Which product categories generate the most completed revenue?",
        ]
    if metric_id in {"order_count", "completed_orders"}:
        return [
            "Show monthly order counts for 2025.",
            "Break completed orders down by country.",
            "Compare order counts by status.",
        ]
    if metric_id == "average_order_value":
        return [
            "Show monthly average completed order value for 2025.",
            "Compare average completed order value by country.",
        ]
    if metric_id == "customer_count":
        return ["Show monthly customer registrations for 2025.", "Show registered customers by country."]
    return [
        "Show this result by month for 2025.",
        "Compare this result by country.",
    ]


def analyze_result(plan: QueryPlan, result: dict, validated: ValidatedSQL) -> ResultAnalysis:
    """Calculate concise insights locally from the bounded query result."""
    context = build_result_context(result, validated)
    metric = METRICS[plan.metric]
    scope = plan.date_range.lower() if plan.date_range != "All available dates" else "all available dates"
    rows = context["rows"]
    columns = context["columns"]
    caveats: list[str] = []

    if context["possibly_truncated"]:
        caveats.append("The query reached the row limit, so rankings and totals may be incomplete.")
    if context["sampled"]:
        caveats.append("Insights use a bounded subset of the returned rows.")
    if not rows:
        return ResultAnalysis(
            answer=f"No matching data was returned for {metric.name.lower()} across {scope}.",
            caveats=caveats,
            follow_up_questions=_follow_ups(metric.id),
        )

    numeric_indexes = [
        index
        for index in range(len(columns))
        if all(row[index] is None or numeric(row[index]) for row in rows)
        and any(row[index] is not None for row in rows)
    ]
    dimension_indexes = [index for index in range(len(columns)) if index not in numeric_indexes]

    if len(rows) == 1 and len(numeric_indexes) == 1 and not dimension_indexes:
        measure_index = numeric_indexes[0]
        value = _number(rows[0][measure_index])
        currency = _measure_currency(metric.currency, columns[measure_index])
        caveats.append(
            "This is one aggregate value; explaining changes or differences requires a time or segment breakdown."
        )
        return ResultAnalysis(
            answer=f"{metric.name} across {scope} is {_format_value(value, currency)}.",
            caveats=caveats,
            follow_up_questions=_follow_ups(metric.id),
        )

    answer = f"{metric.name} returned {context['returned_row_count']:,} grouped results across {scope}."
    findings: list[str] = []
    trends: list[str] = []
    anomalies: list[str] = []
    if not numeric_indexes:
        caveats.append("The returned columns do not contain a numeric measure for automated comparison.")
        return ResultAnalysis(
            answer=answer,
            caveats=caveats,
            follow_up_questions=_follow_ups(metric.id),
        )

    measure_index = numeric_indexes[-1]
    points = [(row, _number(row[measure_index])) for row in rows if row[measure_index] is not None]
    if not points:
        return ResultAnalysis(answer=answer, caveats=caveats, follow_up_questions=_follow_ups(metric.id))

    dimension_index = dimension_indexes[0] if dimension_indexes else None
    measure_name = _humanize(columns[measure_index])
    currency = _measure_currency(metric.currency, columns[measure_index])
    labels = [str(row[dimension_index]) for row, _ in points] if dimension_index is not None else []
    ranked = sorted(points, key=lambda item: item[1], reverse=True)
    top_row, top_value = ranked[0]
    top_label = str(top_row[dimension_index]) if dimension_index is not None else "The highest row"
    top_text = f"{top_label} has the highest {measure_name} at {_format_value(top_value, currency)}"
    additive = metric.id != "average_order_value" and all(value >= 0 for _, value in points)
    total = sum((value for _, value in points), Decimal(0))
    if additive and total > 0:
        top_text += f", representing {(top_value / total * 100):.1f}% of the returned total"
    findings.append(top_text + ".")

    if len(ranked) > 1 and ranked[-1][1] != top_value:
        low_row, low_value = ranked[-1]
        low_label = str(low_row[dimension_index]) if dimension_index is not None else "The lowest row"
        findings.append(f"{low_label} has the lowest {measure_name} at {_format_value(low_value, currency)}.")

    if dimension_index is not None and _is_temporal(columns[dimension_index], labels) and len(points) > 1:
        chronological = sorted(points, key=lambda item: str(item[0][dimension_index]))
        first_value, last_value = chronological[0][1], chronological[-1][1]
        first_label = str(chronological[0][0][dimension_index])
        last_label = str(chronological[-1][0][dimension_index])
        if first_value:
            change = (last_value - first_value) / abs(first_value) * 100
            direction = "increased" if change > 0 else "decreased" if change < 0 else "was unchanged"
            suffix = f" by {abs(change):.1f}%" if change else ""
            trends.append(f"From {first_label} to {last_label}, {measure_name} {direction}{suffix}.")
        trends.append(f"The peak occurred in {top_label} at {_format_value(top_value, currency)}.")

    values = [float(value) for _, value in points]
    if len(values) >= 4:
        q1, _, q3 = quantiles(values, n=4, method="inclusive")
        spread = q3 - q1
        if spread > 0:
            lower, upper = q1 - 1.5 * spread, q3 + 1.5 * spread
            for row, value in points:
                if float(value) < lower or float(value) > upper:
                    label = str(row[dimension_index]) if dimension_index is not None else "A returned row"
                    anomalies.append(
                        f"{label} is outside the 1.5×IQR range at {_format_value(value, currency)}."
                    )
                    if len(anomalies) == 3:
                        break

    return ResultAnalysis(
        answer=answer,
        findings=findings,
        trends=trends,
        anomalies=anomalies,
        caveats=caveats,
        follow_up_questions=_follow_ups(metric.id),
    )
