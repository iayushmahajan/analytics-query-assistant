from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    db_status = "ok"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {str(exc)}"

    return {
        "status": "ok",
        "service": "backend",
        "database": db_status,
    }