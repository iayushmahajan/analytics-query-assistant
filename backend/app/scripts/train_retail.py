"""Leakage-resistant one-week demand evaluation with a transparent baseline."""

import json
import math
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sqlalchemy import text

from app.core.db import engine

LAG_WEEKS = 8
VALIDATION_WEEKS = 8
TEST_WEEKS = 8
MINIMUM_ML_IMPROVEMENT = 0.05


def features(code_index: int, values: list[int], week_number: int) -> list[float]:
    previous = values[week_number - LAG_WEEKS:week_number]
    angle = 2 * math.pi * (week_number % 52) / 52
    return [
        code_index,
        *previous[-4:][::-1],
        mean(previous[-4:]),
        mean(previous),
        sum(value == 0 for value in previous) / LAG_WEEKS,
        math.sin(angle),
        math.cos(angle),
    ]


def _model() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="poisson",
        max_iter=100,
        max_leaf_nodes=12,
        min_samples_leaf=12,
        categorical_features=[0],
        random_state=42,
    )


def _mae(points: list[tuple[date, int, float, float]], prediction_index: int) -> float:
    return mean(abs(point[1] - point[prediction_index]) for point in points)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = math.ceil(probability * len(ordered)) - 1
    return ordered[max(0, min(position, len(ordered) - 1))]


def build_forecasts(rows: list[tuple], codes: list[tuple], last_week: date) -> list[dict]:
    """Select on validation weeks and report metrics on later, untouched test weeks."""
    first_week = min(row[1] for row in rows)
    weeks = []
    current = first_week
    while current <= last_week:
        weeks.append(current)
        current += timedelta(days=7)
    evaluation_weeks = VALIDATION_WEEKS + TEST_WEEKS
    if len(weeks) < LAG_WEEKS + evaluation_weeks + 8:
        raise ValueError("Not enough complete weeks for validation and test windows")

    index = {week: position for position, week in enumerate(weeks)}
    series = {code: [0] * len(weeks) for code, _ in codes}
    for code, week, units in rows:
        if code in series and week in index:
            series[code][index[week]] = max(0, int(units))

    evaluation_start = len(weeks) - evaluation_weeks
    per_code: dict[str, list[tuple[date, int, float, float]]] = defaultdict(list)

    # Expanding-window evaluation: every prediction is fitted only on earlier weeks.
    for origin in range(evaluation_start, len(weeks)):
        train_x, train_y = [], []
        for code_index, (code, _) in enumerate(codes):
            values = series[code]
            for week_index in range(LAG_WEEKS, origin):
                train_x.append(features(code_index, values, week_index))
                train_y.append(values[week_index])
        model = _model().fit(np.asarray(train_x), train_y)
        for code_index, (code, _) in enumerate(codes):
            values = series[code]
            predicted = max(0.0, float(model.predict(np.asarray([
                features(code_index, values, origin)
            ]))[0]))
            baseline = mean(values[origin - 4:origin])
            per_code[code].append((weeks[origin], values[origin], predicted, baseline))

    # Refit on every complete observed week only after the test predictions are fixed.
    final_x, final_y = [], []
    for code_index, (code, _) in enumerate(codes):
        values = series[code]
        for week_index in range(LAG_WEEKS, len(weeks)):
            final_x.append(features(code_index, values, week_index))
            final_y.append(values[week_index])
    final_model = _model().fit(np.asarray(final_x), final_y)
    future_predictions = final_model.predict(np.asarray([
        features(code_index, series[code], len(weeks))
        for code_index, (code, _) in enumerate(codes)
    ]))

    output = []
    for code_index, (code, description) in enumerate(codes):
        validation = per_code[code][:VALIDATION_WEEKS]
        test = per_code[code][VALIDATION_WEEKS:]
        model_validation_mae = _mae(validation, 2)
        baseline_validation_mae = _mae(validation, 3)
        required_mae = baseline_validation_mae * (1 - MINIMUM_ML_IMPROVEMENT)
        method = "gradient_boosting" if model_validation_mae < required_mae else "four_week_average"
        chosen_index = 2 if method == "gradient_boosting" else 3

        test_errors = [point[chosen_index] - point[1] for point in test]
        test_absolute_errors = [abs(value) for value in test_errors]
        test_mae = mean(test_absolute_errors)
        baseline_test_mae = _mae(test, 3)
        total_actual = sum(point[1] for point in test)
        test_wape = sum(test_absolute_errors) / total_actual if total_actual else None
        test_bias = mean(test_errors)

        validation_errors = [abs(point[chosen_index] - point[1]) for point in validation]
        interval_radius = _percentile(validation_errors, 0.8)
        interval_coverage = mean(
            abs(point[chosen_index] - point[1]) <= interval_radius for point in test
        )

        baseline_next = mean(series[code][-4:])
        model_next = max(0.0, float(future_predictions[code_index]))
        chosen = model_next if method == "gradient_boosting" else baseline_next
        confidence = "supported"
        if test_wape is None or test_wape > 0.75 or interval_coverage < 0.5:
            confidence = "insufficient"
        elif test_wape > 0.4 or interval_coverage < 0.7:
            confidence = "limited"

        output.append({
            "stock_code": code,
            "description": description,
            "forecast_week": weeks[-1] + timedelta(days=7),
            "training_cutoff": weeks[-1],
            "predicted_units": round(chosen, 1),
            "prediction_lower": round(max(0.0, chosen - interval_radius), 1),
            "prediction_upper": round(chosen + interval_radius, 1),
            "baseline_units": round(baseline_next, 1),
            "model_mae": round(model_validation_mae, 2),
            "baseline_mae": round(baseline_validation_mae, 2),
            "test_mae": round(test_mae, 2),
            "baseline_test_mae": round(baseline_test_mae, 2),
            "test_wape": round(test_wape, 4) if test_wape is not None else None,
            "test_bias": round(test_bias, 2),
            "interval_coverage": round(interval_coverage, 4),
            "validation_weeks": VALIDATION_WEEKS,
            "test_weeks": TEST_WEEKS,
            "confidence": confidence,
            "method": method,
            "history": [
                {"week": weeks[i].isoformat(), "actual": series[code][i]}
                for i in range(max(0, len(weeks) - 16), len(weeks))
            ],
            "backtest": [
                {
                    "week": week.isoformat(),
                    "actual": actual,
                    "predicted": round(predicted if method == "gradient_boosting" else baseline, 1),
                }
                for week, actual, predicted, baseline in test
            ],
        })
    return output


def main():
    with engine.connect() as connection:
        newest = connection.execute(text(
            "SELECT MAX(invoice_date)::date FROM retail_lines WHERE is_sale"
        )).scalar()
        if not newest:
            raise ValueError("Import the UCI retail data before training")
        # Exclude the dataset's final, incomplete calendar week.
        last_week = newest - timedelta(days=newest.weekday() + 7)
        codes = connection.execute(text("""
            SELECT stock_code, MIN(description)
            FROM retail_lines WHERE is_sale AND invoice_date < :end_date
              AND stock_code ~ '^[0-9A-Za-z]+$'
            GROUP BY stock_code
            HAVING COUNT(DISTINCT date_trunc('week', invoice_date)) >= 32
            ORDER BY SUM(quantity) DESC LIMIT 12
        """), {"end_date": last_week - timedelta(weeks=TEST_WEEKS)}).all()
        if not codes:
            raise ValueError("No products have sufficient history")
        rows = connection.execute(text("""
            SELECT stock_code, date_trunc('week', invoice_date)::date, SUM(quantity)
            FROM retail_lines WHERE is_sale AND invoice_date < :end_date
              AND stock_code = ANY(:codes)
            GROUP BY 1, 2 ORDER BY 2
        """), {
            "end_date": last_week + timedelta(days=7),
            "codes": [code for code, _ in codes],
        }).all()
    forecasts = build_forecasts(rows, codes, last_week)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM retail_forecasts"))
        for forecast in forecasts:
            connection.execute(text("""
                INSERT INTO retail_forecasts
                (stock_code, description, forecast_week, training_cutoff, predicted_units,
                 prediction_lower, prediction_upper, baseline_units, model_mae, baseline_mae,
                 test_mae, baseline_test_mae, test_wape, test_bias, interval_coverage,
                 validation_weeks, test_weeks, confidence, method, history, backtest)
                VALUES (:stock_code, :description, :forecast_week, :training_cutoff,
                        :predicted_units, :prediction_lower, :prediction_upper, :baseline_units,
                        :model_mae, :baseline_mae, :test_mae, :baseline_test_mae, :test_wape,
                        :test_bias, :interval_coverage, :validation_weeks, :test_weeks,
                        :confidence, :method, CAST(:history AS json), CAST(:backtest AS json))
            """), {
                **forecast,
                "history": json.dumps(forecast["history"]),
                "backtest": json.dumps(forecast["backtest"]),
            })
    model_wins = sum(item["method"] == "gradient_boosting" for item in forecasts)
    supported = sum(item["confidence"] == "supported" for item in forecasts)
    print(
        f"Saved {len(forecasts)} forecasts; ML selected for {model_wins}; "
        f"{supported} have supported test evidence"
    )


if __name__ == "__main__":
    main()
