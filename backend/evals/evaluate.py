"""Opt-in live generation evaluation against the isolated golden fixture (no reseeding)."""

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.api.schemas.query import QueryRequest
from app.services.metric_policy import prepare_query
from app.services.sql_executor import SQLExecutionError, execute_select_sql
from app.services.sql_generator import ProviderError, generate_query_plan
from app.services.sql_validator import SQLValidationError

CASES = json.loads((Path(__file__).parent / "golden.json").read_text())


def normalized(rows):
    def cell(value):
        try:
            return str(Decimal(str(value)).normalize())
        except InvalidOperation:
            return str(value)

    return sorted(tuple(cell(v) for v in row) for row in rows)


def evaluate_plan(case, plan, execute=execute_select_sql):
    assert plan.status == case["status"], "Unexpected interpretation status"
    assert plan.metric == case["metric"], "Unexpected canonical metric"
    if plan.status == "needs_clarification":
        assert plan.clarification_question
    if plan.status != "ready":
        assert plan.sql is None
        return
    checked = prepare_query(plan)
    assert set(checked.source_tables) == set(case["tables"]), "Unexpected source tables"
    assert all(f.lower() in " ".join(plan.filters).lower() for f in case["filters"]), (
        "Missing interpreted filter"
    )
    result = execute(checked)
    assert normalized(result["rows"]) == normalized(case["expected"]), "Numeric/result mismatch"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Spend provider requests using configured credentials"
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("Use --live only with the isolated golden fixture database configured")
    passed = 0
    for case in CASES:
        try:
            evaluate_plan(case, generate_query_plan(QueryRequest(question=case["question"])))
            passed += 1
            print("PASS", case["question"])
        except (AssertionError, ProviderError, SQLExecutionError, SQLValidationError) as exc:
            # Evaluation reports failure types, never provider/database contents.
            print("FAIL", case["question"], type(exc).__name__)
    print(f"{passed}/{len(CASES)} passed")
    raise SystemExit(0 if passed == len(CASES) else 1)


if __name__ == "__main__":
    main()
