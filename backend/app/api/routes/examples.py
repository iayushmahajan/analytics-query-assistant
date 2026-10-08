from fastapi import APIRouter

from app.api.schemas.example import ExampleItem

router = APIRouter(prefix="/examples", tags=["examples"])


@router.get("", response_model=list[ExampleItem])
def get_examples():
    return [
        ExampleItem(id=1, question="What were total gross sales across all available dates?"),
        ExampleItem(id=2, question="Show monthly gross sales during 2011."),
        ExampleItem(id=3, question="Which countries generated the most gross sales?"),
        ExampleItem(id=4, question="Which products sold the most units?"),
        ExampleItem(id=5, question="How many sales invoices were there by month in 2011?"),
    ]
