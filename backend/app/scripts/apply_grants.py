"""Grant only the approved analytics surface after migrations, as the table owner."""

from sqlalchemy import text

from app.core.db import engine

STATEMENTS = [
    "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM analytics_reader",
    "GRANT SELECT ON countries, categories, products, orders, order_items TO analytics_reader",
    "GRANT SELECT (id, country_id, created_at) ON customers TO analytics_reader",
    "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM analytics_reader",
]


def main():
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))


if __name__ == "__main__":
    main()
