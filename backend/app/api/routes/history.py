from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.schemas.history import HistoryItem
from app.core.config import settings
from app.core.db import SessionLocal
from app.models import QueryHistory

router = APIRouter(prefix="/history", tags=["history"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=list[HistoryItem])
def get_history(db: Session = Depends(get_db)):
    history = (
        db.query(QueryHistory)
        .order_by(desc(QueryHistory.created_at))
        .limit(settings.QUERY_HISTORY_LIMIT)
        .all()
    )
    return history