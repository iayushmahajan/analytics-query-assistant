import json
import logging

import httpx

from app.core.config import settings
from app.services.prompt_builder import build_sql_generation_messages

logger = logging.getLogger(__name__)


class SQLGenerationError(Exception):
    pass


def generate_sql_and_explanation(question: str) -> dict[str, str]:
    if not settings.GITHUB_MODELS_API_KEY:
        raise SQLGenerationError("GITHUB_MODELS_API_KEY is not set.")

    messages = build_sql_generation_messages(question)

    payload = {
        "model": settings.GITHUB_MODELS_NAME,
        "messages": messages,
        "temperature": 0,
    }

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings.GITHUB_MODELS_API_KEY}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                settings.GITHUB_MODELS_API_URL,
                headers=headers,
                json=payload,
            )
    except Exception as exc:
        logger.exception("GitHub Models request failed")
        raise SQLGenerationError(f"GitHub Models request failed: {str(exc)}") from exc

    if response.status_code >= 400:
        logger.error("GitHub Models error: %s", response.text)
        raise SQLGenerationError(
            f"GitHub Models returned {response.status_code}: {response.text}"
        )

    try:
        data = response.json()
    except Exception as exc:
        logger.exception("Failed to parse GitHub Models response")
        raise SQLGenerationError("GitHub Models returned invalid JSON.") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.exception("GitHub Models response missing expected fields")
        raise SQLGenerationError("GitHub Models response format was unexpected.") from exc

    if not content:
        raise SQLGenerationError("GitHub Models returned an empty response.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.exception("Failed to parse model JSON content")
        raise SQLGenerationError("Model returned invalid JSON content.") from exc

    generated_sql = str(parsed.get("generated_sql", "")).strip()
    explanation = str(parsed.get("explanation", "")).strip()
    status = str(parsed.get("status", "generated")).strip()

    if not generated_sql:
        raise SQLGenerationError("Generated SQL is empty.")

    if not explanation:
        explanation = "SQL generated successfully."

    if not status:
        status = "generated"

    return {
        "generated_sql": generated_sql,
        "explanation": explanation,
        "status": status,
    }