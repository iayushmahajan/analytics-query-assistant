import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas.query import QueryRequest, QueryResponse
from app.core.db import SessionLocal
from app.models import QueryHistory
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
) -> QueryHistory:
    history_item = QueryHistory(
        question=question,
        generated_sql=generated_sql,
        explanation=explanation,
        status=status,
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
            )

            return QueryResponse(
                id=history_item.id,
                question=history_item.question,
                generated_sql=history_item.generated_sql,
                explanation=history_item.explanation,
                status=history_item.status,
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
        safe_sql = generated["generated_sql"]
        final_status = "blocked"
        final_explanation = (
            f"{generated['explanation']} Validation blocked this SQL: {str(exc)}"
        )

    history_item = save_history_item(
        db=db,
        question=payload.question,
        generated_sql=safe_sql,
        explanation=final_explanation,
        status=final_status,
    )

    return QueryResponse(
        id=history_item.id,
        question=history_item.question,
        generated_sql=history_item.generated_sql,
        explanation=history_item.explanation,
        status=history_item.status,
        created_at=history_item.created_at,
    )