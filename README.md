# Analytics Query Assistant

A full-stack portfolio application for **trustworthy AI-powered sales analytics**. Ask a business question, clarify ambiguity, inspect the metric definition, and explore actual PostgreSQL results through findings, charts, KPI cards, tables and SQL.

The dataset is **synthetic, single-currency EUR sales data**. This is a shared demonstration workspace, not a private enterprise BI service.

## What it does

- Typed query interpretation: canonical metric, dimensions, filters, date range, assumptions and explanation.
- Clarification before execution; `needs_clarification` never runs SQL. Up to three clarification turns travel with the original question.
- PostgreSQL SQL parsed with SQLGlot, a restricted analytics role, read-only transactions, outer row caps and timeouts.
- Canonical completed-order population enforced structurally for revenue, AOV and completed-sales metrics, even if generated SQL omits the status filter.
- A second, separate AI call analyzes a bounded result context. Query results remain available if findings generation fails.
- Dataset coverage and real health status, numeric KPI cards for single-row results, line/bar charts for compatible two-column results, sortable tables and CSV export.
- Inspectable assumptions, filters, actual SQL source tables and formatted SQL with copy support.
- History restores bounded result snapshots and findings without rerunning either AI stage.
- Deterministic demo seeding, database constraints, Alembic migrations, adversarial tests and 18 golden evaluation cases.

## Architecture

```mermaid
flowchart TD
    U[React workspace] --> Q[FastAPI POST /query]
    Q --> G[Typed interpretation + SQL generation]
    M[Canonical metrics + schema] --> G
    G -->|needs_clarification| U
    G -->|ready| V[SQLGlot validation + canonical population policy]
    V --> R[Restricted PostgreSQL reader / read-only transaction]
    R --> B[Bounded result / privacy filtering]
    B --> A[Result-aware AI analysis / no database tools]
    A --> H[Application DB connection / history snapshot]
    H --> U
```

The existing architecture remains a React application and a small FastAPI service. No agent framework, queues, vector database or microservices are used.

| Layer | Stack |
|---|---|
| Frontend | React 19, strict TypeScript, Vite 8, Tailwind 3, Axios, Recharts |
| Backend | Python 3.11, FastAPI, Pydantic 2, SQLAlchemy, HTTPX |
| AI | GitHub Models chat completions, default `openai/gpt-4.1` |
| Database | PostgreSQL 16, psycopg2, Alembic |
| Quality | pytest, Ruff, Vitest, Testing Library, Playwright, GitHub Actions |
| Deployment | Docker Compose, Uvicorn, multi-stage frontend build served by Nginx |

## Quick start: Docker

Requires Docker with Compose. Preserve an existing `.env`; merge missing settings from the example rather than overwriting it.

```bash
cp .env.example .env  # only for a new installation
# Edit .env: set three distinct URL-safe database passwords and GITHUB_MODELS_API_KEY.
# Generate each password with: openssl rand -hex 24

docker compose up --build -d
docker compose run --rm backend python -m app.scripts.seed
```

Open **http://localhost:5173**. The API is proxied under `/api`; OpenAPI documentation is at `/api/docs` (the interactive schema is available at `/api/openapi.json`). Database and backend ports are not published by default.

The migration service waits for PostgreSQL, upgrades the schema and applies reader grants. The normal application does not create, drop or seed tables. A new database is empty until the explicit seed command runs. Missing AI credentials are reported as degraded health; metadata/history still work, while analysis requests return a clear configuration error.

The default seed contains 250 customers, 24 products, eight countries and roughly 2,000 orders over **2024–2025**, plus their line items. For meaningful time charts, ask for 2025 rather than the current year. Dates and monetary totals are deterministic. All customer registrations precede orders. There are no refunds, taxes, discounts or currency conversions.

**Destructive demo reset, only for disposable data:**

```bash
docker compose run --rm backend python -m app.scripts.seed --reset-demo
```

This truncates business data **and history**. It never runs during startup. `docker compose down` retains the volume; `down -v` deletes it.

## Configuration

See [`.env.example`](.env.example). Never commit populated environment files.

| Variable | Purpose / default |
|---|---|
| `POSTGRES_PASSWORD` | Local bootstrap administrator password; Compose only |
| `APP_DB_PASSWORD` | Application/table-owner password; Compose only |
| `ANALYTICS_DB_PASSWORD` | Restricted reader password; Compose only |
| `DATABASE_URL` | Application writes and migrations; direct/local development |
| `ANALYTICS_DATABASE_URL` | Restricted analytics connection; direct/local development |
| `GITHUB_MODELS_API_KEY` | Provider credential, backend only |
| `GITHUB_MODELS_NAME` | `openai/gpt-4.1` |
| `GITHUB_MODELS_API_URL` | GitHub Models chat-completions endpoint |
| `MAX_SQL_ROWS` | 100; permitted configuration 1–1,000 |
| `SQL_STATEMENT_TIMEOUT_MS` | 5,000; permitted configuration 100–30,000 |
| `MAX_RESULT_BYTES` | 200,000 for serialized result rows |
| `ANALYSIS_MAX_ROWS` / `ANALYSIS_MAX_BYTES` | 30 rows / 12,000 bytes of result context |
| `QUERY_HISTORY_LIMIT` | 20 recent entries, maximum 100 |
| `CORS_ALLOWED_ORIGINS` | Comma-separated browser origins for direct API access |
| `VITE_API_BASE_URL` | `/api`; set at frontend build time for separate hosting |
| `API_ROOT_PATH` | Empty for direct access; `/api` behind the Compose reverse proxy |
| `APP_ENV` / `LOG_LEVEL` | Environment label / log level |

Compose constructs its connection URLs from the three password variables, overriding legacy `DATABASE_URL` values in `.env`. Use URL-safe passwords. Existing deployments require provisioning the reader role and grants before switching to the new query path. `database/init.sh` runs only on an **empty** PostgreSQL volume.

## Local development without Docker application containers

Provision PostgreSQL and the two roles first. [`database/init.sh`](database/init.sh) shows the bootstrap permissions and reads passwords from environment variables; run it through an administrative PostgreSQL connection for a new `analytics_db` database. Configure the two URLs in `.env` for the application owner and reader respectively.

```bash
cd backend
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.scripts.apply_grants
python -m app.scripts.seed
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to `localhost:8000`. For host access to the Compose database, explicitly add a loopback port mapping in a local Compose override; the default deployment deliberately keeps it internal.

## Metrics and interpretation

[`backend/app/constants/metrics.py`](backend/app/constants/metrics.py) is the typed semantic catalog. Definitions are included in the generation prompt and returned with the analysis.

| Metric | Canonical meaning |
|---|---|
| Revenue / completed revenue | Sum of completed order totals |
| Order count | Distinct orders across all statuses unless explicitly filtered |
| Completed orders | Distinct completed orders |
| Average order value | Completed order revenue divided by completed order count, at order grain |
| Customer count | Distinct registered customers; registration date applies |
| Product / category sales | Completed line-item quantity × historical unit price; product quantity uses quantity sums |
| Country / region sales | Completed order totals grouped through customer country |

Revenue and completed-sales metrics rewrite each actual `orders` source into a completed-order subquery before a second SQL validation pass. This enforces the canonical population, including nested queries and unions. It is **not** proof that every join, grouping or calculation is correct. SQL must still avoid double-counting order totals after line-item joins. The UI distinguishes canonical rules and SQL-derived source tables from AI-interpreted filters.

Unspecified dates mean all available dates. Important unresolved terms such as “performance” trigger clarification. A ready response requires a canonical metric and SQL; non-ready responses cannot carry executable SQL. User continuation is treated as untrusted input, not a system instruction.

## SQL and database security

The application policy parses exactly one PostgreSQL query. It permits analytical SELECTs, joins, aggregations, nonrecursive CTEs, nested queries and safe set operations. It rejects mutation/DDL, SELECT INTO, locking and transaction commands, unauthorized schemas/tables, application history, system catalogs, unknown functions, dangerous casts and recursive CTEs. Scope-aware table checks distinguish CTE aliases from actual tables. Quoted names, comments and literals cannot bypass structural checks.

Outer limits are added/capped on the root AST; a nested LIMIT or `'limit 1'` string has no effect on the outer cap. SQL size and AST complexity are bounded. Fetching also checks row count, column count, unique column names and serialized size. Decimal values remain strings in JSON to preserve exact database precision.

The reader has:

- No superuser, role-creation or database-creation privileges.
- No schema creation or temporary-table privilege.
- SELECT on the five non-customer business tables; column-level SELECT on `customers.id`, `country_id`, `created_at` only.
- No access to names, emails, history or application sequences.
- Default read-only transactions, a statement timeout, lock timeout and constrained search path.

Each execution additionally starts a read-only transaction, applies its configured timeout/search path and checks for accidentally elevated credentials. SQL failures roll back the analytics transaction before history is written through the independent application connection. The reader's object permissions remain restrictive even if transaction read-only mode is disabled.

The role/grant setup assumes a dedicated demonstration database with no untrusted extension functions or additional role memberships. Application/table-owner credentials are trusted administration credentials and are never used for model SQL. PostgreSQL built-in functions are also limited by the application allowlist; row caps do not eliminate expensive query plans, so timeouts remain necessary.

## AI findings and privacy

Generation and result analysis both require validated Pydantic JSON contracts. Provider outages, malformed JSON, rate limits and timeouts become stable public errors; raw provider/database messages are not returned. Findings failure is a warning on an otherwise successful result.

The second stage has **no execution tools**. It receives only the selected metric, currency and a bounded result sample. It receives no original question, raw SQL or free-text plan. For any query referencing customers, only numeric result columns are shared, with generic labels; customer-related textual dimensions are deliberately omitted. This also limits the specificity of geographic findings. Other business result labels may be shared. Sampling and possible truncation are disclosed.

The first stage necessarily receives the question and clarification text. Do not enter confidential information. The application is intended for synthetic data and shares history between visitors; authentication and private workspaces are intentionally out of scope.

## Database and migrations

Business tables: `countries`, `customers`, `categories`, `products`, `orders`, `order_items`. `query_history` stores request metadata and a bounded JSON response snapshot containing interpretation, results, findings and timings. Legacy entries remain visible but cannot restore nonexistent snapshots.

- `0001`: original schema baseline.
- `0002`: history snapshots, status checks and positive/nonnegative quantity/price/amount constraints.
- Normal startup never invokes `create_all` or drops data.
- After migrations, run `python -m app.scripts.apply_grants` as the table owner (automatic in Compose).

**Existing original schema:** back up first, verify it matches revision `0001`, then run `alembic stamp 0001` followed by `alembic upgrade head`. Do not stamp an empty database. Invalid existing rows must be corrected before adding constraints. Role bootstrap is separate from schema migration; old volumes do not rerun initialization scripts.

## API and observability

| Route | Purpose |
|---|---|
| `POST /query` | Question plus optional clarification turns; executes only a ready validated plan |
| `GET /history` | Recent shared request summaries |
| `GET /history/{id}` | Saved response snapshot; no rerun |
| `GET /examples` | Starter questions |
| `GET /metadata` | Actual date coverage/order count, currency, metric catalog |
| `GET /health` | Database availability, reader restrictions, provider configuration |

Health returns 503 when required checks fail. Provider status is **configured, not live-probed**. Every request gets an `X-Request-ID`. JSON logs include status/failure category, request ID and timings without questions, result rows, SQL, API keys or raw exception messages. Generation, SQL and analysis timings are separate; response processing time excludes the final history commit/network delivery, while HTTP logs measure the complete handler duration.

## Tests and evaluation

```bash
cd backend
ruff check .
python -m compileall -q app
pytest -q

cd ../frontend
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Backend unit/API tests mock external provider calls. PostgreSQL integration tests are opt-in locally and run in CI against a disposable PostgreSQL service. They verify clean migrations, model/schema agreement, deterministic seeding, constraints, permission denial, timeout rollback, independent history writes, row caps and numeric golden answers.

**Integration tests erase their configured test database contents.** Set these only for a dedicated disposable database with provisioned roles:

```bash
export TEST_DATABASE_URL='postgresql://analytics_app:TEST_PASSWORD@localhost:5432/analytics_db'
export TEST_ANALYTICS_DATABASE_URL='postgresql://analytics_reader:TEST_PASSWORD@localhost:5432/analytics_db'
export TEST_ALLOW_RESET=1
cd backend
pytest -q
```

The 18 cases in [`backend/evals/golden.json`](backend/evals/golden.json) cover revenue, counts, AOV, products, categories, geography, time ranges, status filters, ambiguity and out-of-scope/mutating requests. Each records expected semantics and, where applicable, independently specified numeric results on a six-order fixture. Automated tests execute reference plans against PostgreSQL and compare normalized result sets, not exact SQL strings. This validates the reference semantics and execution pipeline; it **does not measure live model accuracy**.

For a deliberate live model evaluation, load `backend/evals/fixture.sql` **only into an isolated disposable database**, set the application/reader URLs and real provider key, then run:

```bash
cd backend
python -m evals.evaluate --live
```

This spends up to 18 generation requests and checks returned plans/results against the same expectations. It does not auto-reseed or call the findings model. The live suite was not run during this upgrade.

Frontend component tests cover success, clarification, history, errors, clipboard denial, CSV safety and chart-shape selection. Chromium tests cover category and time-series charts, mobile overflow, clarification continuation, CSV download, history restoration and failed-query clearing. Their API responses are mocked; they are not live-provider browser tests.

GitHub Actions runs Python checks plus PostgreSQL integration, frontend lint/types/tests/build, Chromium workflows and Docker image builds. It verifies changes; it does not automatically deploy or push commits.

## Limitations

- AI-selected joins, calculations and findings can still be wrong. Canonical definitions, status enforcement and evaluation improve reliability but do not prove arbitrary analytical correctness.
- The fixed function/schema allowlist intentionally rejects unsupported SQL. There is no automatic SQL repair loop or arbitrary database connection/upload support.
- Snapshot and analysis caps can truncate results; charts describe returned rows, not an unobserved complete population. Charts require one textual/date dimension and one numeric measure; other shapes use tables. KPI cards reflect actual single-row numeric values.
- History is shared and retained until an explicit demo reset; no authentication, quotas or multi-tenancy. Do not expose it as a private business-data service.
- Provider readiness is configuration-only. Real provider credentials, quota and model availability must be verified in the deployment environment.
- Tailwind 3's development dependency chain retains an npm advisory for deeply nested glob-pattern denial of service (`braces`). Compatible fixes were applied elsewhere; clearing this remaining build-tool advisory requires a Tailwind major migration. The Nginx runtime ships compiled static assets, not these Node build dependencies. Build only trusted source/configuration.

For the upgrade verification record and environment-specific Docker limitations, see [docs/verification.md](docs/verification.md).
