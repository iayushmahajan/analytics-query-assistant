from fastapi import APIRouter

from app.api.schemas.example import ExampleItem

router = APIRouter(prefix="/examples", tags=["examples"])


@router.get("", response_model=list[ExampleItem])
def get_examples():
    return [
        ExampleItem(id=1, question="What is total completed revenue?"),
        ExampleItem(id=2, question="Show monthly completed revenue for 2025."),
        ExampleItem(id=3, question="Break completed revenue down by country."),
        ExampleItem(id=4, question="What is the average completed order value?"),
        ExampleItem(id=5, question="Which product categories generate the most completed revenue?"),
        ExampleItem(id=6, question="Which products sold the most units on completed orders?"),
        ExampleItem(id=7, question="Show completed orders by country."),
        ExampleItem(id=8, question="Compare order counts by status during 2025."),
        ExampleItem(id=9, question="Show monthly customer registrations for 2025."),
        ExampleItem(id=10, question="Show registered customers by country."),
    ]
