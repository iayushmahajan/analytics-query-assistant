"""Repeatable import of Germany's monthly retail volume index from Eurostat."""

import argparse
import hashlib
import hmac
import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.core.db import engine

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_trtu_m"
FILTERS = {
    "format": "JSON",
    "lang": "en",
    "freq": "M",
    "geo": "DE",
    "nace_r2": "G47",
    "s_adj": "SCA",
    "unit": "I21",
    "indic_bt": "VOL_SLS",
}
SOURCE_URL = f"{BASE_URL}?{urllib.parse.urlencode(FILTERS)}"
MAX_RESPONSE_BYTES = 5_000_000
MIN_OBSERVATIONS = 120


@dataclass(frozen=True)
class MarketSnapshot:
    observations: list[dict]
    source_updated_at: datetime
    missing_periods: int


def download_payload() -> bytes:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "retail-analytics-forecasting/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("Eurostat response exceeded the expected size")
    return payload


def payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _category_codes(document: dict, dimension: str) -> list[str]:
    index = document["dimension"][dimension]["category"]["index"]
    if isinstance(index, dict):
        return [code for code, _ in sorted(index.items(), key=lambda item: item[1])]
    if isinstance(index, list):
        return index
    raise ValueError(f"Unexpected Eurostat category index for {dimension}")


def parse_payload(payload: bytes) -> MarketSnapshot:
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Eurostat returned invalid JSON") from exc
    if document.get("class") != "dataset" or document.get("version") != "2.0":
        raise ValueError("Unexpected Eurostat JSON-stat response")
    expected_ids = ["freq", "indic_bt", "nace_r2", "s_adj", "unit", "geo", "time"]
    if document.get("id") != expected_ids or len(document.get("size", [])) != len(expected_ids):
        raise ValueError("Eurostat dataset dimensions changed")
    expected_codes = {
        "freq": "M",
        "indic_bt": "VOL_SLS",
        "nace_r2": "G47",
        "s_adj": "SCA",
        "unit": "I21",
        "geo": "DE",
    }
    for dimension, expected in expected_codes.items():
        if _category_codes(document, dimension) != [expected]:
            raise ValueError(f"Unexpected Eurostat selection for {dimension}")

    periods = _category_codes(document, "time")
    if document["size"][-1] != len(periods):
        raise ValueError("Eurostat time dimension size is inconsistent")
    raw_values = document.get("value", {})
    if isinstance(raw_values, list):
        values = {str(i): value for i, value in enumerate(raw_values) if value is not None}
    elif isinstance(raw_values, dict):
        values = raw_values
    else:
        raise ValueError("Eurostat values are missing")
    statuses = document.get("status", {})
    observations = []
    for position, period_text in enumerate(periods):
        raw_value = values.get(str(position))
        if raw_value is None:
            continue
        try:
            period = datetime.strptime(period_text, "%Y-%m").date().replace(day=1)
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Eurostat contains an invalid period or value") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Eurostat retail index must contain finite positive values")
        status = statuses.get(str(position)) if isinstance(statuses, dict) else None
        observations.append({"period": period, "value": round(value, 3), "status": status})
    if len(observations) < MIN_OBSERVATIONS:
        raise ValueError("Eurostat response has too few usable monthly observations")
    if any(left["period"] >= right["period"] for left, right in zip(observations, observations[1:])):
        raise ValueError("Eurostat periods are not strictly increasing")
    try:
        updated = datetime.fromisoformat(document["updated"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Eurostat response is missing a valid update timestamp") from exc
    return MarketSnapshot(
        observations=observations,
        source_updated_at=updated,
        missing_periods=len(periods) - len(observations),
    )


def import_snapshot(snapshot: MarketSnapshot, digest: str) -> None:
    latest = snapshot.observations[-1]
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM market_forecasts"))
        connection.execute(text("DELETE FROM market_observations"))
        connection.execute(
            text("""
                INSERT INTO market_observations (period, value, status)
                VALUES (:period, :value, :status)
            """),
            snapshot.observations,
        )
        connection.execute(text("""
            INSERT INTO market_imports
            (source, source_sha256, source_updated_at, observation_count,
             missing_periods, latest_period, latest_status)
            VALUES (:source, :digest, :updated, :count, :missing, :latest, :status)
        """), {
            "source": SOURCE_URL,
            "digest": digest,
            "updated": snapshot.source_updated_at,
            "count": len(snapshot.observations),
            "missing": snapshot.missing_periods,
            "latest": latest["period"],
            "status": latest["status"],
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
        f"Imported {len(snapshot.observations)} Germany retail-index months through "
        f"{snapshot.observations[-1]['period']:%Y-%m}; source SHA-256 {digest}"
    )


if __name__ == "__main__":
    main()
