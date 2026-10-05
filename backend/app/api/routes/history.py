from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.schemas.history import HistoryItem
from app.api.schemas.query import QueryResponse
from app.core.config import settings
from app.core.db import get_db
from app.models import QueryHistory

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[HistoryItem])
def get_history(db: Session = Depends(get_db)):
    return (
        db.query(QueryHistory)
        .order_by(desc(QueryHistory.created_at))
        .limit(settings.QUERY_HISTORY_LIMIT)
        .all()
    )


@router.get("/{item_id}", response_model=QueryResponse)
def get_history_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(QueryHistory, item_id)
    if not item:
        raise HTTPException(404, "History item not found.")
    if not item.snapshot:
        raise HTTPException(409, "This legacy entry has no saved result. Run the question again.")
    return QueryResponse.model_validate(item.snapshot)
