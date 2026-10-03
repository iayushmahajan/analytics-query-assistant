import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.api.schemas.query import QueryPlan, QueryRequest
from app.core.config import settings
from app.services.prompt_builder import build_sql_generation_messages

T = TypeVar("T", bound=BaseModel)


class ProviderError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 502):
        self.code = code
        self.http_status = http_status
        super().__init__(message)


def structured_completion(messages: list[dict[str, str]], contract: type[T]) -> T:
    if not settings.GITHUB_MODELS_API_KEY:
        raise ProviderError("provider_not_configured", "The AI provider is not configured.", 503)
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(settings.GITHUB_MODELS_API_URL,
                headers={"Authorization": f"Bearer {settings.GITHUB_MODELS_API_KEY}",
                         "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                json={"model": settings.GITHUB_MODELS_NAME, "messages": messages,
                      "temperature": 0, "max_tokens": 2500,
                      "response_format": {"type": "json_object"}})
    except httpx.TimeoutException as exc:
        raise ProviderError("provider_timeout", "The AI provider timed out. Please try again.", 504) from exc
    except httpx.HTTPError as exc:
        raise ProviderError("provider_unavailable", "The AI provider is unavailable.", 503) from exc
    if response.status_code == 429:
        raise ProviderError("provider_rate_limited", "AI request limit reached. Please try again later.", 429)
    if response.is_error:
        raise ProviderError("provider_unavailable", "The AI provider could not complete the request.", 503)
    try:
        if len(response.content) > 100000:
            raise ValueError("Oversized response")
        content = response.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("Expected text")
        return contract.model_validate_json(content, strict=True)
    except (ValueError, TypeError, KeyError, IndexError, ValidationError, json.JSONDecodeError) as exc:
        raise ProviderError("invalid_model_output", "The AI response did not match the required format. Please try again.") from exc


def generate_query_plan(request: QueryRequest) -> QueryPlan:
    return structured_completion(build_sql_generation_messages(request), QueryPlan)
