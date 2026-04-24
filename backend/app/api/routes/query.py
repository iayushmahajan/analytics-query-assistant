import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas.query import QueryRequest, QueryResponse
from app.core.db import SessionLocal
from app.models import QueryHistory
from app.services.sql_executor import SQLExecutionError, execute_select_sql
from app.services.sql_generator import SQLGenerationError, generate_sql_and_explanation
from app.services.sql_validator import SQLValidationError, validate_and_sanitize_sql

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_history_item(
    db: Session,
    question: str,
    generated_sql: str,
    explanation: str,
    status: str,
    row_count: int | None = None,
    execution_time_ms: int | None = None,
) -> QueryHistory:
    history_item = QueryHistory(
        question=question,
        generated_sql=generated_sql,
        explanation=explanation,
        status=status,
        row_count=row_count,
        execution_time_ms=execution_time_ms,
    )
    db.add(history_item)
    db.commit()
    db.refresh(history_item)
    return history_item


@router.post("", response_model=QueryResponse)
def create_query(payload: QueryRequest, db: Session = Depends(get_db)):
    logger.info("Received query generation request")

    try:
        generated = generate_sql_and_explanation(payload.question)
    except SQLGenerationError as exc:
        error_message = str(exc)

        if error_message == "Generated SQL is empty.":
            logger.warning("Model returned empty SQL. Marking request as blocked.")

            history_item = save_history_item(
                db=db,
                question=payload.question,
                generated_sql="",
                explanation="The request could not be converted into a safe read-only SQL query.",
                status="blocked",
                row_count=0,
                execution_time_ms=0,
            )

            return QueryResponse(
                id=history_item.id,
                question=history_item.question,
                generated_sql="",
                explanation=history_item.explanation,
                status=history_item.status,
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=0,
                created_at=history_item.created_at,
            )

        logger.error("SQL generation failed: %s", error_message)
        raise HTTPException(status_code=500, detail=error_message) from exc

    try:
        safe_sql = validate_and_sanitize_sql(generated["generated_sql"])
        final_status = "validated" if generated["status"] == "generated" else generated["status"]
        final_explanation = generated["explanation"]
    except SQLValidationError as exc:
        logger.warning("SQL validation blocked query: %s", str(exc))

        blocked_explanation = (
            f"{generated['explanation']} Validation blocked this request: {str(exc)}"
        )

        history_item = save_history_item(
            db=db,
            question=payload.question,
            generated_sql="",
            explanation=blocked_explanation,
            status="blocked",
            row_count=0,
            execution_time_ms=0,
        )

        return QueryResponse(
            id=history_item.id,
            question=history_item.question,
            generated_sql="",
            explanation=history_item.explanation,
            status=history_item.status,
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=0,
            created_at=history_item.created_at,
        )

    try:
        execution_result = execute_select_sql(db, safe_sql)
    except SQLExecutionError as exc:
        logger.error("SQL execution failed: %s", str(exc))

        history_item = save_history_item(
            db=db,
            question=payload.question,
            generated_sql=safe_sql,
            explanation=f"{final_explanation} Execution failed: {str(exc)}",
            status="execution_failed",
            row_count=0,
            execution_time_ms=0,
        )

        return QueryResponse(
            id=history_item.id,
            question=history_item.question,
            generated_sql=history_item.generated_sql,
            explanation=history_item.explanation,
            status=history_item.status,
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=0,
            created_at=history_item.created_at,
        )

    history_item = save_history_item(
        db=db,
        question=payload.question,
        generated_sql=safe_sql,
        explanation=final_explanation,
        status=final_status,
        row_count=execution_result["row_count"],
        execution_time_ms=execution_result["execution_time_ms"],
    )

    return QueryResponse(
        id=history_item.id,
        question=history_item.question,
        generated_sql=history_item.generated_sql,
        explanation=history_item.explanation,
        status=history_item.status,
        columns=execution_result["columns"],
        rows=execution_result["rows"],
        row_count=execution_result["row_count"],
        execution_time_ms=execution_result["execution_time_ms"],
        created_at=history_item.created_at,
    )