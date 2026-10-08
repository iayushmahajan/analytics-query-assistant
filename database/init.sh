#!/bin/sh
set -eu
# Runs only when PostgreSQL initializes an empty volume. Values are quoted by psql.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set db_name="$POSTGRES_DB" --set app_password="$APP_DB_PASSWORD" \
  --set reader_password="$ANALYTICS_DB_PASSWORD" <<'SQL'
CREATE ROLE analytics_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD :'app_password';
CREATE ROLE analytics_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD :'reader_password';
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db_name" TO analytics_app, analytics_reader;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO analytics_app;
GRANT USAGE ON SCHEMA public TO analytics_reader;
ALTER ROLE analytics_reader SET default_transaction_read_only = on;
ALTER ROLE analytics_reader SET statement_timeout = '5s';
ALTER ROLE analytics_reader SET lock_timeout = '1s';
ALTER ROLE analytics_reader SET search_path = pg_catalog, public;
SQL
