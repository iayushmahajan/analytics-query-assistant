"""Grant only the approved analytics surface after migrations, as the table owner."""

from sqlalchemy import text

from app.core.db import engine

STATEMENTS = [
    "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM analytics_reader",
    "GRANT SELECT ON retail_lines, retail_forecasts, retail_imports TO analytics_reader",
    "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM analytics_reader",
]


def main():
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))


if __name__ == "__main__":
    main()
