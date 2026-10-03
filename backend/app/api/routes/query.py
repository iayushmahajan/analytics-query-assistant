from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.schemas.query import QueryRequest, QueryResponse
from app.core.db import get_db
from app.services.query_workflow import run_analysis

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def create_query(payload: QueryRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    result, response.status_code = run_analysis(payload, db, request.state.request_id)
    return result
