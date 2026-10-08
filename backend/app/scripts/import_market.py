"""Import and enrich one curated Eurostat retail-market dataset."""

import argparse
import hashlib
import hmac
import itertools
import json
import math
import statistics
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import text

from app.core.db import engine

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_trtu_m"
EU_GEOS = (
    "EU27_2020", "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE",
    "EL", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
)
CATEGORIES = (
    "G47",
    "G47_FOOD",
    "G47_NFOOD_X_G473",
    "G473",
)
CATEGORY_NAMES = {
    "G47": "Total retail",
    "G47_FOOD": "Food, beverages and tobacco",
    "G47_NFOOD_X_G473": "Non-food excluding fuel",
    "G473": "Automotive fuel",
}
FILTERS = [
    ("format", "JSON"),
    ("lang", "en"),
    ("freq", "M"),
    ("indic_bt", "VOL_SLS"),
    ("s_adj", "SCA"),
    ("unit", "I21"),
    ("sinceTimePeriod", "2015-01"),
    *(("nace_r2", category) for category in CATEGORIES),
    *(("geo", geography) for geography in EU_GEOS),
]
SOURCE_URL = f"{BASE_URL}?{urllib.parse.urlencode(FILTERS)}"
MAX_RESPONSE_BYTES = 20_000_000
MIN_OBSERVATIONS = 8_000
EXPECTED_DIMENSIONS = ["freq", "indic_bt", "nace_r2", "s_adj", "unit", "geo", "time"]


@dataclass(frozen=True)
class RetailSnapshot:
    observations: list[dict]
    source_updated_at: datetime
    missing_cells: int
    earliest_period: date
    latest_period: date


def download_payload() -> bytes:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "eurostat-retail-intelligence/1.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("Eurostat response exceeded the expected size")
    return payload


def payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _category_codes(document: dict, dimension: str) -> list[str]:
    try:
        index = document["dimension"][dimension]["category"]["index"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Eurostat response is missing dimension {dimension}") from exc
    if isinstance(index, dict):
        return [code for code, _ in sorted(index.items(), key=lambda item: item[1])]
    if isinstance(index, list):
        return index
    raise ValueError(f"Unexpected Eurostat category index for {dimension}")


def _category_labels(document: dict, dimension: str) -> dict[str, str]:
    category = document["dimension"][dimension]["category"]
    labels = category.get("label", {})
    return labels if isinstance(labels, dict) else {}


def _sparse_values(value, expected_cells: int) -> dict[int, object]:
    if isinstance(value, list):
        if len(value) != expected_cells:
            raise ValueError("Eurostat value array size is inconsistent")
        return {index: item for index, item in enumerate(value) if item is not None}
    if isinstance(value, dict):
        try:
            output = {int(index): item for index, item in value.items() if item is not None}
        except (TypeError, ValueError) as exc:
            raise ValueError("Eurostat value positions are invalid") from exc
        if any(index < 0 or index >= expected_cells for index in output):
            raise ValueError("Eurostat value position is outside the declared dimensions")
        return output
    raise ValueError("Eurostat values are missing")


def _sparse_status(value, expected_cells: int) -> dict[int, str]:
    if value is None:
        return {}
    if isinstance(value, list):
        if len(value) != expected_cells:
            raise ValueError("Eurostat status array size is inconsistent")
        return {index: str(item) for index, item in enumerate(value) if item is not None}
    if isinstance(value, dict):
        try:
            output = {int(index): str(item) for index, item in value.items() if item is not None}
        except (TypeError, ValueError) as exc:
            raise ValueError("Eurostat status positions are invalid") from exc
        if any(index < 0 or index >= expected_cells for index in output):
            raise ValueError("Eurostat status position is outside the declared dimensions")
        return output
    raise ValueError("Eurostat statuses have an unexpected shape")


def _month_before(current: date) -> date:
    return date(current.year - (current.month == 1), 12 if current.month == 1 else current.month - 1, 1)


def _year_before(current: date) -> date:
    return date(current.year - 1, current.month, 1)


def add_derived_metrics(observations: list[dict]) -> None:
    series: dict[tuple[str, str], list[dict]] = {}
    for row in observations:
        series.setdefault((row["geo_code"], row["category_code"]), []).append(row)
    for rows in series.values():
        rows.sort(key=lambda row: row["period"])
        by_period = {row["period"]: row for row in rows}
        changes: list[float] = []
        for row in rows:
            previous = by_period.get(_month_before(row["period"]))
            year_ago = by_period.get(_year_before(row["period"]))
            monthly_change = row["value"] - previous["value"] if previous else None
            yearly_change = row["value"] - year_ago["value"] if year_ago else None
            row["monthly_change"] = round(monthly_change, 3) if monthly_change is not None else None
            row["yearly_change"] = round(yearly_change, 3) if yearly_change is not None else None
            recent = changes[-12:]
            row["rolling_volatility"] = (
                round(statistics.pstdev(recent), 3) if len(recent) >= 3 else None
            )
            baseline = changes[-36:]
            score = None
            if monthly_change is not None and len(baseline) >= 12:
                center = statistics.median(baseline)
                mad = statistics.median(abs(item - center) for item in baseline)
                if mad > 0:
                    score = (monthly_change - center) / (1.4826 * mad)
            row["anomaly_score"] = round(score, 3) if score is not None else None
            row["is_anomaly"] = bool(score is not None and abs(score) >= 3.5)
            if monthly_change is not None:
                changes.append(monthly_change)


def parse_payload(payload: bytes) -> RetailSnapshot:
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Eurostat returned invalid JSON") from exc
    if document.get("class") != "dataset" or document.get("version") != "2.0":
        raise ValueError("Unexpected Eurostat JSON-stat response")
    if document.get("id") != EXPECTED_DIMENSIONS:
        raise ValueError("Eurostat dataset dimensions changed")
    sizes = document.get("size")
    if not isinstance(sizes, list) or len(sizes) != len(EXPECTED_DIMENSIONS):
        raise ValueError("Eurostat dimension sizes are invalid")
    codes = {dimension: _category_codes(document, dimension) for dimension in EXPECTED_DIMENSIONS}
    expected_fixed = {
        "freq": ["M"],
        "indic_bt": ["VOL_SLS"],
        "s_adj": ["SCA"],
        "unit": ["I21"],
    }
    for dimension, expected in expected_fixed.items():
        if codes[dimension] != expected:
            raise ValueError(f"Unexpected Eurostat selection for {dimension}")
    if set(codes["nace_r2"]) != set(CATEGORIES) or len(codes["nace_r2"]) != len(CATEGORIES):
        raise ValueError("Eurostat retail category selection changed")
    if set(codes["geo"]) != set(EU_GEOS) or len(codes["geo"]) != len(EU_GEOS):
        raise ValueError("Eurostat geography selection changed")
    if sizes != [len(codes[dimension]) for dimension in EXPECTED_DIMENSIONS]:
        raise ValueError("Eurostat dimension sizes are inconsistent")

    expected_cells = math.prod(sizes)
    values = _sparse_values(document.get("value"), expected_cells)
    statuses = _sparse_status(document.get("status"), expected_cells)
    geo_labels = _category_labels(document, "geo")
    observations: list[dict] = []
    seen: set[tuple[str, str, date]] = set()
    for coordinates in itertools.product(*(range(size) for size in sizes)):
        position = 0
        for coordinate, size in zip(coordinates, sizes, strict=True):
            position = position * size + coordinate
        if position not in values:
            continue
        selected = {
            dimension: codes[dimension][coordinate]
            for dimension, coordinate in zip(EXPECTED_DIMENSIONS, coordinates, strict=True)
        }
        try:
            period = datetime.strptime(selected["time"], "%Y-%m").date().replace(day=1)
            value = float(values[position])
        except (TypeError, ValueError) as exc:
            raise ValueError("Eurostat contains an invalid period or value") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Eurostat retail index must contain finite positive values")
        key = (selected["geo"], selected["nace_r2"], period)
        if key in seen:
            raise ValueError("Eurostat contains duplicate retail observations")
        seen.add(key)
        observations.append({
            "geo_code": selected["geo"],
            "geography": "EU-27" if selected["geo"] == "EU27_2020" else geo_labels[selected["geo"]],
            "category_code": selected["nace_r2"],
            "category": CATEGORY_NAMES[selected["nace_r2"]],
            "period": period,
            "value": round(value, 3),
            "status": statuses.get(position),
        })
    if len(observations) < MIN_OBSERVATIONS:
        raise ValueError("Eurostat response has too few usable observations")
    periods = [row["period"] for row in observations]
    if min(periods) < date(2015, 1, 1):
        raise ValueError("Eurostat response contains data outside the requested period")
    try:
        updated = datetime.fromisoformat(document["updated"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Eurostat response is missing a valid update timestamp") from exc
    add_derived_metrics(observations)
    return RetailSnapshot(
        observations=observations,
        source_updated_at=updated,
        missing_cells=expected_cells - len(observations),
        earliest_period=min(periods),
        latest_period=max(periods),
    )


def import_snapshot(snapshot: RetailSnapshot, digest: str) -> None:
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM retail_observations"))
        connection.execute(text("""
            INSERT INTO retail_observations
            (geo_code, geography, category_code, category, period, value, status,
             monthly_change, yearly_change, rolling_volatility, anomaly_score, is_anomaly)
            VALUES (:geo_code, :geography, :category_code, :category, :period, :value, :status,
                    :monthly_change, :yearly_change, :rolling_volatility, :anomaly_score,
                    :is_anomaly)
        """), snapshot.observations)
        connection.execute(text("""
            INSERT INTO retail_imports
            (source, source_sha256, source_updated_at, observation_count, missing_cells,
             earliest_period, latest_period, geography_count, category_count)
            VALUES (:source, :digest, :updated, :count, :missing, :earliest, :latest,
                    :geographies, :categories)
        """), {
            "source": SOURCE_URL,
            "digest": digest,
            "updated": snapshot.source_updated_at,
            "count": len(snapshot.observations),
            "missing": snapshot.missing_cells,
            "earliest": snapshot.earliest_period,
            "latest": snapshot.latest_period,
            "geographies": len({row["geo_code"] for row in snapshot.observations}),
            "categories": len({row["category_code"] for row in snapshot.observations}),
        })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, help="Use a saved Eurostat JSON response")
    parser.add_argument(
        "--expected-sha256",
        help="Abort before import unless the response has this SHA-256 digest",
    )
    args = parser.parse_args()
    payload = args.payload.read_bytes() if args.payload else download_payload()
    digest = payload_sha256(payload)
    if args.expected_sha256 and not hmac.compare_digest(digest, args.expected_sha256.lower()):
        raise ValueError("Response SHA-256 does not match --expected-sha256; database was not changed")
    snapshot = parse_payload(payload)
    import_snapshot(snapshot, digest)
    print(
        f"Imported {len(snapshot.observations)} Eurostat retail observations through "
        f"{snapshot.latest_period:%Y-%m}; source SHA-256 {digest}"
    )


if __name__ == "__main__":
    main()
