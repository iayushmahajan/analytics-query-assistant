from sqlalchemy import text


def reader_is_restricted(connection) -> bool:
    """Fail closed on accidentally configured owner/superuser credentials."""
    return bool(
        connection.execute(
            text("""
        SELECT NOT (rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls)
          AND NOT has_schema_privilege(current_user, 'public', 'CREATE')
          AND NOT has_table_privilege(current_user, 'public.query_history', 'SELECT')
          AND NOT has_table_privilege(current_user, 'public.orders', 'INSERT,UPDATE,DELETE,TRUNCATE')
          AND NOT has_column_privilege(current_user, 'public.customers', 'email', 'SELECT')
        FROM pg_roles WHERE rolname = current_user
    """)
        ).scalar()
    )
