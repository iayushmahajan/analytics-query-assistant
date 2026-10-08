from fastapi import APIRouter

from app.api.schemas.example import ExampleItem

router = APIRouter(prefix="/examples", tags=["examples"])


@router.get("", response_model=list[ExampleItem])
def get_examples():
    return [
        ExampleItem(id=1, question="How has Germany's total retail index changed since 2021?"),
        ExampleItem(id=2, question="Compare Germany and the EU-27 over the latest 12 months."),
        ExampleItem(id=3, question="Which EU countries have the strongest latest annual change?"),
        ExampleItem(id=4, question="Compare Germany's four retail categories in the latest month."),
        ExampleItem(id=5, question="Show unusual German retail movements since 2024."),
    ]
