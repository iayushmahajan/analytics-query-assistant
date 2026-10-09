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


def _column_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def shape_comparison_result(plan: QueryPlan, result: dict) -> dict:
    """Pivot complete long-form time comparisons into auditable side-by-side rows."""
    if result["possibly_truncated"] or len(result["rows"]) < 2:
        return result
    columns = result["columns"]
    period_index = next(
        (index for index, column in enumerate(columns) if column.lower() in {"period", "date", "month"}),
        None,
    )
    entity_index = next(
        (index for index, column in enumerate(columns) if column.lower() in {"geography", "category"}),
        None,
    )
    if period_index is None or entity_index is None:
        return result
    measure_indexes = [
        index for index in range(len(columns)) if index not in {period_index, entity_index}
    ]
    if len(measure_indexes) != 1:
        return result
    measure_index = measure_indexes[0]
    if not all(
        isinstance(row[period_index], str)
        and isinstance(row[entity_index], str)
        and (row[measure_index] is None or numeric(row[measure_index]))
        for row in result["rows"]
    ):
        return result

    entities = sorted({str(row[entity_index]) for row in result["rows"]})
    if set(entities) == {"Germany", "EU-27"}:
        entities = ["Germany", "EU-27"]
    if len(entities) != 2:
        return result
    by_period: dict[str, dict[str, object]] = {}
    for row in result["rows"]:
        period, entity = str(row[period_index]), str(row[entity_index])
        if entity in by_period.setdefault(period, {}):
            return result
        by_period[period][entity] = row[measure_index]
    if any(set(values) != set(entities) for values in by_period.values()):
        return result

    measure = columns[measure_index].lower()
    suffix = "index" if measure == "value" and plan.metric == "retail_index" else measure
    output_columns = [columns[period_index], *[f"{_column_slug(item)}_{suffix}" for item in entities]]
    output_columns.append(f"{_column_slug(entities[0])}_minus_{_column_slug(entities[1])}_gap")
    output_rows = []
    for period in sorted(by_period):
        values = [by_period[period][entity] for entity in entities]
        gap = None
        if values[0] is not None and values[1] is not None:
            gap = str(_number(values[0]) - _number(values[1]))
        output_rows.append([period, *values, gap])
    return {
        **result,
        "columns": output_columns,
        "rows": output_rows,
        "row_count": len(output_rows),
    }


def _series_name(column: str) -> str:
    stem = re.sub(r"_(?:index|value|monthly_change|yearly_change)$", "", column.lower())
    if stem == "germany":
        return "Germany"
    if stem in {"eu27", "eu_27"}:
        return "EU-27"
    return _humanize(stem).title()


def _indexed_movement(start: Decimal, end: Decimal) -> str:
    change = end - start
    if not change:
        return f"was unchanged at {_format_value(end, None)}"
    direction = "increased" if change > 0 else "decreased"
    sign = "+" if change > 0 else "-"
    relative = abs(change / start * 100) if start else None
    relative_text = (
        f"; about {sign}{relative:.1f}% relative to the starting month" if relative is not None else ""
    )
    return (
        f"{direction} from {_format_value(start, None)} to {_format_value(end, None)} "
        f"({sign}{_format_value(abs(change), None)} index points{relative_text})"
    )


def _reference_position(value: Decimal) -> str:
    difference = value - Decimal(100)
    if difference > 0:
        return f"{_format_value(difference, None)}% above"
    if difference < 0:
        return f"{_format_value(abs(difference), None)}% below"
    return "equal to"


def _analyze_time_comparison(
    metric_name: str,
    scope: str,
    columns: list[str],
    rows: list[list],
    dimension_index: int,
    numeric_indexes: list[int],
) -> ResultAnalysis | None:
    series_indexes = [
        index
        for index in numeric_indexes
        if not any(token in columns[index].lower() for token in ("gap", "minus", "difference"))
    ]
    if len(series_indexes) != 2:
        return None
    complete = [row for row in rows if all(row[index] is not None for index in series_indexes)]
    if len(complete) < 2:
        return None
    chronological = sorted(complete, key=lambda row: str(row[dimension_index]))
    first, last = chronological[0], chronological[-1]
    first_period, last_period = str(first[dimension_index]), str(last[dimension_index])
    names = [_series_name(columns[index]) for index in series_indexes]
    first_values = [_number(first[index]) for index in series_indexes]
    last_values = [_number(last[index]) for index in series_indexes]
    changes = [last_values[index] - first_values[index] for index in range(2)]
    latest_gap = last_values[0] - last_values[1]
    first_gap = first_values[0] - first_values[1]
    relation = "above" if latest_gap > 0 else "below" if latest_gap < 0 else "equal to"
    comparable = len(chronological)
    first_above = sum(
        _number(row[series_indexes[0]]) > _number(row[series_indexes[1]]) for row in chronological
    )
    relative_change = changes[0] - changes[1]
    relative_word = "outperformed" if relative_change > 0 else "underperformed" if relative_change < 0 else "matched"
    gap_change = abs(latest_gap) - abs(first_gap)
    gap_word = "widened" if gap_change > 0 else "narrowed" if gap_change < 0 else "was unchanged"
    if metric_name == "retail_index":
        answer = (
            f"From {first_period} to {last_period}, {names[0]} "
            f"{_indexed_movement(first_values[0], last_values[0])}, while {names[1]} "
            f"{_indexed_movement(first_values[1], last_values[1])}."
        )
    else:
        answer = (
            f"From {first_period} to {last_period}, {names[0]} changed by "
            f"{_format_value(changes[0], None)} points, while {names[1]} changed by "
            f"{_format_value(changes[1], None)} points."
        )
    findings = [
        f"In {last_period}, {names[0]} was {_format_value(abs(latest_gap), None)} index points "
        f"{relation} {names[1]} ({_format_value(last_values[0], None)} versus "
        f"{_format_value(last_values[1], None)}).",
        f"{names[0]} was above {names[1]} in {first_above} of {comparable} comparable months.",
    ]
    if metric_name == "retail_index":
        findings.insert(
            1,
            f"Against the 2021=100 baseline, {names[0]}'s latest level was "
            f"{_reference_position(last_values[0])} the 2021 average and {names[1]}'s was "
            f"{_reference_position(last_values[1])} it.",
        )
    trends = [
        f"Over the window, {names[0]} {relative_word} {names[1]} by "
        f"{_format_value(abs(relative_change), None)} index points.",
        f"The absolute gap {gap_word} from {_format_value(abs(first_gap), None)} to "
        f"{_format_value(abs(latest_gap), None)} index points.",
    ]
    return ResultAnalysis(
        answer=answer,
        findings=findings,
        trends=trends,
        follow_up_questions=[
            f"In which month was the gap between {names[0]} and {names[1]} widest?",
            f"Compare {names[0]} and {names[1]} annual movement in the latest month.",
            f"Compare {names[0]} and {names[1]} volatility over this period.",
        ],
    )


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

    dimension_index = dimension_indexes[0] if dimension_indexes else None
    labels = [str(row[dimension_index]) for row in rows] if dimension_index is not None else []
    if (
        dimension_index is not None
        and _is_temporal(columns[dimension_index], labels)
        and len(numeric_indexes) >= 2
    ):
        comparison = _analyze_time_comparison(
            metric.id, scope, columns, rows, dimension_index, numeric_indexes
        )
        if comparison:
            comparison.caveats.extend(caveats)
            return comparison

    measure_index = numeric_indexes[-1]
    points = [(row, _number(row[measure_index])) for row in rows if row[measure_index] is not None]
    if not points:
        return ResultAnalysis(answer=answer, caveats=caveats, follow_up_questions=_follow_ups(metric.id))

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
