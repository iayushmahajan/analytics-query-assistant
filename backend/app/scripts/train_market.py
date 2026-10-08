"""One-month German retail-volume forecast with nested chronological evaluation."""

import json
import math
from datetime import date
from statistics import mean

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sqlalchemy import text

from app.core.db import engine

LAG_MONTHS = 12
VALIDATION_MONTHS = 24
TEST_MONTHS = 24
MIN_HISTORY_MONTHS = 120
MINIMUM_ML_IMPROVEMENT = 0.05


def month_after(value: date) -> date:
    return date(value.year + (value.month == 12), value.month % 12 + 1, 1)


def contiguous_suffix(observations: list[tuple[date, float, str | None]]) -> list[tuple[date, float, str | None]]:
    if not observations:
        return []
    ordered = sorted(observations, key=lambda item: item[0])
    suffix = [ordered[-1]]
    for item in reversed(ordered[:-1]):
        if month_after(item[0]) != suffix[0][0]:
            break
        suffix.insert(0, item)
    return suffix


def features(values: list[float], origin: int, period: date) -> list[float]:
    previous = values[origin - LAG_MONTHS:origin]
    angle = 2 * math.pi * (period.month - 1) / 12
    return [
        *previous[::-1],
        mean(previous[-3:]),
        mean(previous[-6:]),
        mean(previous),
        previous[-1] - previous[-2],
        previous[-1] - previous[-12],
        math.sin(angle),
        math.cos(angle),
        origin / 12,
    ]


def _model() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=120,
        max_leaf_nodes=10,
        min_samples_leaf=12,
        l2_regularization=1.0,
        random_state=42,
    )


def _fit_predict(values: list[float], periods: list[date], origin: int) -> float:
    train_x = [features(values, index, periods[index]) for index in range(LAG_MONTHS, origin)]
    train_y = values[LAG_MONTHS:origin]
    model = _model().fit(np.asarray(train_x), train_y)
    return float(model.predict(np.asarray([features(values, origin, periods[origin])]))[0])


def _baselines(values: list[float], origin: int) -> dict[str, float]:
    return {
        "last_value": values[origin - 1],
        "three_month_average": mean(values[origin - 3:origin]),
        "year_ago": values[origin - 12],
    }


def _mae(actual: list[float], predicted: list[float]) -> float:
    return mean(abs(observed - estimate) for observed, estimate in zip(actual, predicted, strict=True))


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = math.ceil(probability * len(ordered)) - 1
    return ordered[max(0, min(position, len(ordered) - 1))]


def build_forecast(observations: list[tuple[date, float, str | None]]) -> dict:
    series = contiguous_suffix(observations)
    if len(series) < MIN_HISTORY_MONTHS:
        raise ValueError(
            f"Need {MIN_HISTORY_MONTHS} contiguous monthly observations; found {len(series)}"
        )
    periods = [item[0] for item in series]
    values = [float(item[1]) for item in series]
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("Retail index observations must be finite and positive")

    evaluation_months = VALIDATION_MONTHS + TEST_MONTHS
    evaluation_start = len(values) - evaluation_months
    points = []
    for origin in range(evaluation_start, len(values)):
        points.append({
            "period": periods[origin],
            "actual": values[origin],
            "gradient_boosting": _fit_predict(values, periods, origin),
            **_baselines(values, origin),
        })
    validation = points[:VALIDATION_MONTHS]
    test = points[VALIDATION_MONTHS:]
    baseline_methods = ("last_value", "three_month_average", "year_ago")
    baseline_method = min(
        baseline_methods,
        key=lambda method: _mae(
            [point["actual"] for point in validation],
            [point[method] for point in validation],
        ),
    )
    validation_actual = [point["actual"] for point in validation]
    ml_validation = [point["gradient_boosting"] for point in validation]
    baseline_validation = [point[baseline_method] for point in validation]
    ml_validation_mae = _mae(validation_actual, ml_validation)
    baseline_validation_mae = _mae(validation_actual, baseline_validation)
    method = (
        "gradient_boosting"
        if ml_validation_mae < baseline_validation_mae * (1 - MINIMUM_ML_IMPROVEMENT)
        else baseline_method
    )

    test_actual = [point["actual"] for point in test]
    test_selected = [point[method] for point in test]
    test_baseline = [point[baseline_method] for point in test]
    test_errors = [estimate - actual for actual, estimate in zip(test_actual, test_selected, strict=True)]
    test_absolute_errors = [abs(error) for error in test_errors]
    test_mae = mean(test_absolute_errors)
    baseline_test_mae = _mae(test_actual, test_baseline)
    test_wape = sum(test_absolute_errors) / sum(test_actual)
    test_bias = mean(test_errors)

    validation_selected = [point[method] for point in validation]
    validation_errors = [
        abs(actual - estimate)
        for actual, estimate in zip(validation_actual, validation_selected, strict=True)
    ]
    interval_radius = _percentile(validation_errors, 0.8)
    interval_coverage = mean(abs(error) <= interval_radius for error in test_errors)

    target_period = month_after(periods[-1])
    ml_next = _fit_predict(values, periods + [target_period], len(values))
    baseline_next = _baselines(values, len(values))[baseline_method]
    predicted = ml_next if method == "gradient_boosting" else _baselines(values, len(values))[method]
    confidence = "supported"
    if test_wape > 0.08 or interval_coverage < 0.5:
        confidence = "insufficient"
    elif test_wape > 0.04 or interval_coverage < 0.7:
        confidence = "limited"

    return {
        "geo_code": "DE",
        "target_period": target_period,
        "training_cutoff": periods[-1],
        "predicted_index": round(predicted, 3),
        "prediction_lower": round(max(0.0, predicted - interval_radius), 3),
        "prediction_upper": round(predicted + interval_radius, 3),
        "baseline_index": round(baseline_next, 3),
        "method": method,
        "baseline_method": baseline_method,
        "validation_mae": round(ml_validation_mae, 3),
        "baseline_validation_mae": round(baseline_validation_mae, 3),
        "test_mae": round(test_mae, 3),
        "baseline_test_mae": round(baseline_test_mae, 3),
        "test_wape": round(test_wape, 5),
        "test_bias": round(test_bias, 3),
        "interval_coverage": round(interval_coverage, 5),
        "confidence": confidence,
        "validation_months": VALIDATION_MONTHS,
        "test_months": TEST_MONTHS,
        "latest_observation_status": series[-1][2],
        "history": [
            {"period": period.isoformat(), "actual": round(value, 3)}
            for period, value, _ in series[-60:]
        ],
        "backtest": [
            {
                "period": point["period"].isoformat(),
                "actual": round(point["actual"], 3),
                "predicted": round(point[method], 3),
            }
            for point in test
        ],
    }


def main() -> None:
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT period, value, status FROM market_observations ORDER BY period
        """)).all()
    forecast = build_forecast([(row[0], float(row[1]), row[2]) for row in rows])
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM market_forecasts"))
        connection.execute(text("""
            INSERT INTO market_forecasts
            (geo_code, target_period, training_cutoff, predicted_index, prediction_lower,
             prediction_upper, baseline_index, method, baseline_method, validation_mae,
             baseline_validation_mae, test_mae, baseline_test_mae, test_wape, test_bias,
             interval_coverage, confidence, validation_months, test_months,
             latest_observation_status, history, backtest)
            VALUES (:geo_code, :target_period, :training_cutoff, :predicted_index,
                    :prediction_lower, :prediction_upper, :baseline_index, :method,
                    :baseline_method, :validation_mae, :baseline_validation_mae,
                    :test_mae, :baseline_test_mae, :test_wape, :test_bias,
                    :interval_coverage, :confidence, :validation_months, :test_months,
                    :latest_observation_status, CAST(:history AS json), CAST(:backtest AS json))
        """), {
            **forecast,
            "history": json.dumps(forecast["history"]),
            "backtest": json.dumps(forecast["backtest"]),
        })
    print(
        f"Saved Germany {forecast['target_period']:%Y-%m} retail-volume forecast: "
        f"{forecast['predicted_index']} ({forecast['confidence']} evidence, "
        f"test WAPE {forecast['test_wape']:.1%})"
    )


if __name__ == "__main__":
    main()
