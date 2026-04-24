import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Analytics Query Assistant API")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@db:5432/analytics_db",
    )
    QUERY_HISTORY_LIMIT: int = int(os.getenv("QUERY_HISTORY_LIMIT", "20"))

    GITHUB_MODELS_API_KEY: str = os.getenv("GITHUB_MODELS_API_KEY", "")
    GITHUB_MODELS_API_URL: str = os.getenv(
        "GITHUB_MODELS_API_URL",
        "https://models.github.ai/inference/chat/completions",
    )
    GITHUB_MODELS_NAME: str = os.getenv("GITHUB_MODELS_NAME", "openai/gpt-4.1")

    MAX_SQL_ROWS: int = int(os.getenv("MAX_SQL_ROWS", "100"))


settings = Settings()