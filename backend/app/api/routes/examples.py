from fastapi import APIRouter

from app.api.schemas.example import ExampleItem

router = APIRouter(prefix="/examples", tags=["examples"])


@router.get("", response_model=list[ExampleItem])
def get_examples():
    return [
        ExampleItem(id=1, question="Show total revenue by country."),
        ExampleItem(id=2, question="What is the average completed order value?"),
        ExampleItem(id=3, question="Show monthly revenue for 2025."),
        ExampleItem(id=4, question="Which product categories generate the most revenue?"),
        ExampleItem(id=5, question="Show completed orders by country."),
        ExampleItem(id=6, question="Which products were ordered the most by quantity?"),
    ]
