import os

from dotenv import load_dotenv

load_dotenv()


def parse_csv_env(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Retail Analytics & Demand Forecasting Platform API")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    API_ROOT_PATH: str = os.getenv("API_ROOT_PATH", "")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://analytics_app@localhost:5432/analytics_db",
    )

    ANALYTICS_DATABASE_URL: str = os.getenv(
        "ANALYTICS_DATABASE_URL", "postgresql://analytics_reader@localhost:5432/analytics_db"
    )
    SQL_STATEMENT_TIMEOUT_MS: int = int(os.getenv("SQL_STATEMENT_TIMEOUT_MS", "5000"))
    MAX_RESULT_BYTES: int = int(os.getenv("MAX_RESULT_BYTES", "200000"))
    ANALYSIS_MAX_ROWS: int = int(os.getenv("ANALYSIS_MAX_ROWS", "30"))
    ANALYSIS_MAX_BYTES: int = int(os.getenv("ANALYSIS_MAX_BYTES", "12000"))

    QUERY_HISTORY_LIMIT: int = int(os.getenv("QUERY_HISTORY_LIMIT", "20"))

    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "foundry_local")
    AI_API_URL: str = os.getenv("AI_API_URL", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "phi-4-mini")
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "120"))

    MAX_SQL_ROWS: int = int(os.getenv("MAX_SQL_ROWS", "100"))

    CORS_ALLOWED_ORIGINS: list[str] = parse_csv_env(
        os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5173",
        )
    )

    CORS_ALLOWED_ORIGIN_REGEX: str | None = os.getenv(
        "CORS_ALLOWED_ORIGIN_REGEX",
        None,
    )


settings = Settings()
if not (1 <= settings.MAX_SQL_ROWS <= 1000):
    raise ValueError("MAX_SQL_ROWS must be between 1 and 1000")
if not (100 <= settings.SQL_STATEMENT_TIMEOUT_MS <= 30000):
    raise ValueError("SQL_STATEMENT_TIMEOUT_MS must be between 100 and 30000")
if not (1 <= settings.ANALYSIS_MAX_ROWS <= 100 and 1000 <= settings.ANALYSIS_MAX_BYTES <= 50000):
    raise ValueError("Invalid analysis context limits")

if not (1000 <= settings.MAX_RESULT_BYTES <= 1000000 and 1 <= settings.QUERY_HISTORY_LIMIT <= 100):
    raise ValueError("Invalid result snapshot or history limit")
if settings.AI_PROVIDER not in {"foundry_local", "groq"}:
    raise ValueError("AI_PROVIDER must be foundry_local or groq")
if not (10 <= settings.AI_REQUEST_TIMEOUT_SECONDS <= 600):
    raise ValueError("AI_REQUEST_TIMEOUT_SECONDS must be between 10 and 600")
