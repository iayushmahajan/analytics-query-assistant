import logging
import time
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.schemas.query import AppError, QueryRequest, QueryResponse
from app.constants.metrics import RETAIL_METRICS
from app.models import QueryHistory
from app.services.metric_policy import prepare_query
from app.services.result_analysis import analyze_result, shape_comparison_result
from app.services.sql_executor import SQLExecutionError, execute_select_sql
from app.services.sql_generator import ProviderError, generate_query_plan
from app.services.sql_validator import SQLValidationError

logger = logging.getLogger(__name__)


def persist_response(db: Session, response: QueryResponse) -> None:
    item = QueryHistory(
        question=response.question,
        generated_sql=response.generated_sql,
        explanation=response.plan.explanation if response.plan else "Request failed before interpretation.",
        status=response.status,
        row_count=response.row_count,
        execution_time_ms=response.timings.execution_ms,
        created_at=response.created_at,
    )
    try:
        db.add(item)
        db.flush()
        response.id = item.id
        item.snapshot = response.model_dump(mode="json")
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        response.id = None
        response.warnings.append("This analysis could not be saved to history.")
        logger.warning("history_write_failed", extra={"request_id": response.request_id})


def run_analysis(payload: QueryRequest, db: Session, request_id: str) -> tuple[QueryResponse, int]:
    start = time.perf_counter()
    response = QueryResponse(
        request_id=request_id,
        question=payload.question,
        dataset=payload.dataset,
        clarification=payload.clarification,
        status="failed",
        created_at=datetime.now(timezone.utc),
    )
    http_status = 200
    stage = time.perf_counter()
    try:
        plan = generate_query_plan(payload)
        response.timings.generation_ms = round((time.perf_counter() - stage) * 1000)
        response.plan = plan
        response.metric_definition = RETAIL_METRICS.get(plan.metric)
        if plan.status != "ready":
            response.status = plan.status
        else:
            validated = prepare_query(plan)
            plan.source_tables = validated.source_tables
            response.generated_sql = validated.sql
            stage = time.perf_counter()
            try:
                result = execute_select_sql(validated)
            finally:
                response.timings.execution_ms = round((time.perf_counter() - stage) * 1000)
            presented_result = shape_comparison_result(plan, result)
            for key in ("columns", "rows", "row_count", "possibly_truncated"):
                setattr(response, key, presented_result[key])
            response.status = "success"
            stage = time.perf_counter()
            try:
                response.analysis = analyze_result(plan, presented_result, validated)
            except (ArithmeticError, ValueError, TypeError, IndexError):
                response.warnings.append("Results are available, but automated insights could not be calculated.")
                logger.warning(
                    "analysis_unavailable",
                    extra={"request_id": request_id, "error_code": "insight_calculation_failed"},
                )
            finally:
                response.timings.analysis_ms = round((time.perf_counter() - stage) * 1000)
    except ProviderError as exc:
        response.timings.generation_ms = round((time.perf_counter() - stage) * 1000)
        response.error = AppError(code=exc.code, message=str(exc))
        http_status = exc.http_status
    except SQLValidationError as exc:
        response.status = "blocked"
        response.error = AppError(code="sql_rejected", message=str(exc))
    except SQLExecutionError as exc:
        response.error = AppError(code=exc.code, message=str(exc))
        http_status = 504 if exc.code == "query_timeout" else 422
    response.timings.total_ms = round((time.perf_counter() - start) * 1000)
    persist_response(db, response)
    logger.info(
        "analysis_completed",
        extra={
            "request_id": request_id,
            "status": response.status,
            "error_code": response.error.code if response.error else None,
            "timings": response.timings.model_dump(),
        },
    )
    return response, http_status
