from pydantic import BaseModel


class ExampleItem(BaseModel):
    id: int
    question: str