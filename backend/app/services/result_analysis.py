import json
import re
from decimal import Decimal, InvalidOperation

from app.api.schemas.query import QueryPlan, ResultAnalysis
from app.constants.metrics import RETAIL_METRICS
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


def _format_measure(value: Decimal, metric_id: str, column: str) -> str:
    formatted = _format_value(value, None)
    if metric_id in {"monthly_change", "yearly_change"} or "change" in column.lower():
        return f"{formatted} index points"
    return formatted


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
    _ = metric_id
    return [
        "Compare Germany and the EU-27 over the latest 12 months.",
        "Which EU countries have the strongest latest annual change?",
        "Show unusual German retail movements since 2024.",
    ]


def analyze_result(plan: QueryPlan, result: dict, validated: ValidatedSQL) -> ResultAnalysis:
    """Calculate concise insights locally from the bounded query result."""
    context = build_result_context(result, validated)
    metric = RETAIL_METRICS[plan.metric]
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

    if len(rows) == 1 and len(numeric_indexes) == 1:
        measure_index = numeric_indexes[0]
        value = _number(rows[0][measure_index])
        measure = _format_measure(value, metric.id, columns[measure_index])
        label = str(rows[0][dimension_indexes[0]]) if dimension_indexes else scope
        reference = " (2021=100)" if metric.id == "retail_index" else ""
        findings: list[str] = []
        if metric.id == "retail_index":
            distance = value - Decimal(100)
            position = "above" if distance > 0 else "below" if distance < 0 else "at"
            if distance:
                findings.append(
                    f"The observation is {_format_value(abs(distance), None)} index points "
                    f"{position} the 2021 reference level."
                )
            else:
                findings.append("The observation equals the 2021 reference level.")
        return ResultAnalysis(
            answer=f"{metric.name} for {label} is {measure}{reference}.",
            findings=findings,
            caveats=caveats,
            follow_up_questions=_follow_ups(metric.id),
        )

    answer = f"{metric.name}: {context['returned_row_count']:,} returned rows for {scope}."
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
    labels = [str(row[dimension_index]) for row, _ in points] if dimension_index is not None else []
    ranked = sorted(points, key=lambda item: item[1], reverse=True)
    top_row, top_value = ranked[0]
    top_label = str(top_row[dimension_index]) if dimension_index is not None else "The highest row"
    findings.append(
        f"{top_label} has the highest {measure_name} at "
        f"{_format_measure(top_value, metric.id, columns[measure_index])}."
    )

    if len(ranked) > 1 and ranked[-1][1] != top_value:
        low_row, low_value = ranked[-1]
        low_label = str(low_row[dimension_index]) if dimension_index is not None else "The lowest row"
        findings.append(
            f"{low_label} has the lowest {measure_name} at "
            f"{_format_measure(low_value, metric.id, columns[measure_index])}."
        )

    if dimension_index is not None and _is_temporal(columns[dimension_index], labels) and len(points) > 1:
        chronological = sorted(points, key=lambda item: str(item[0][dimension_index]))
        first_value, last_value = chronological[0][1], chronological[-1][1]
        first_label = str(chronological[0][0][dimension_index])
        last_label = str(chronological[-1][0][dimension_index])
        if first_value:
            change = (last_value - first_value) / abs(first_value) * 100
            direction = "increased" if change > 0 else "decreased" if change < 0 else "was unchanged"
            point_change = last_value - first_value
            suffix = (
                f" by {_format_value(abs(point_change), None)} index points ({abs(change):.1f}%)"
                if change else ""
            )
            trends.append(f"From {first_label} to {last_label}, {measure_name} {direction}{suffix}.")
        trends.append(
            f"The highest returned level occurred in {top_label} at "
            f"{_format_measure(top_value, metric.id, columns[measure_index])}."
        )

    if metric.id == "retail_anomaly_score":
        for row, value in sorted(points, key=lambda item: abs(item[1]), reverse=True)[:3]:
            if abs(value) >= Decimal("3.5"):
                label = str(row[dimension_index]) if dimension_index is not None else "A returned row"
                anomalies.append(
                    f"{label} exceeds the declared anomaly threshold with a robust score of "
                    f"{_format_value(value, None)}."
                )

    return ResultAnalysis(
        answer=answer,
        findings=findings,
        trends=trends,
        anomalies=anomalies,
        caveats=caveats,
        follow_up_questions=_follow_ups(metric.id),
    )
