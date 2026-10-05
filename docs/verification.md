# Upgrade verification

Final verification: 5 October 2026. All database checks used disposable databases; the existing application database and populated `.env` were preserved.

## Results

| Check | Result |
|---|---|
| Python 3.11 / PostgreSQL 16 backend suite | **89 passed**, one upstream Starlette/AnyIO deprecation warning |
| Ruff and Python compilation | Passed |
| Frontend ESLint and TypeScript | Passed |
| Vitest component/unit tests | **10 passed** |
| Production frontend build | Passed |
| Playwright Chromium desktop/mobile workflows | **2 passed** |
| Backend production/test and frontend Docker builds | Passed |
| Compose configuration, migrations, startup, service health | Passed |
| Nginx → API → mock provider HTTP → PostgreSQL smoke | Passed |
| Live GitHub Models smoke | **Failed: JSON decoding**, safely returned `invalid_model_output` / HTTP 502 |
| Live 18-case model evaluation | Not run |
| Remote GitHub Actions execution | Not run; changes were not pushed |

Backend checks cover AST bypass attempts, clarification execution gating, typed provider failures, bounded/private analysis context, snapshots, clean migrations and model agreement, deterministic seeds, constraints, database permission denial, timeouts/rollback, result limits, and golden numeric answers. The 18 golden cases use reference plans against a six-order PostgreSQL fixture in automated tests; this is not a measured live-model accuracy score.

Browser tests use mocked API responses. The separate container smoke used a local deterministic HTTP provider and real PostgreSQL data, including 1,975 seeded orders. Its completed-revenue query returned **EUR 656,582.37**. It checked health, metadata, proxied Swagger/OpenAPI, both provider stages, snapshot restoration, clarification continuation and unsafe SQL rejection. The provider's ready SQL intentionally omitted the completed-status predicate so the application policy had to enforce it.

Two explicitly authorized live synthetic-data requests were attempted. Generation failed before SQL execution or findings generation; the diagnostic request identified `JSONDecodeError`. No raw response or credential was logged, and the evidence does not establish whether the provider envelope or embedded content caused the decoding failure. A successful live provider round trip remains unverified. The parser was not relaxed to hide this failure.

## Commands

Frontend, from `frontend/`:

```bash
npm run lint && npm run typecheck && npm test && npm run build && npm run test:e2e
```

Backend checks:

```bash
backend/.venv/bin/ruff check backend
PYTHONPYCACHEPREFIX=/tmp/analytics-upgrade-pycache backend/.venv/bin/python -m compileall -q backend/app
```

The existing local virtual environment uses Python 3.10; the authoritative full test run used the Python 3.11 Docker test image. The final source was copied into the disposable test container before running `pytest -q`:

```bash
docker create --name analytics-upgrade-final-checks \
  --network analytics-upgrade-check \
  -e TEST_DATABASE_URL=postgresql://analytics_app:isolated_test_app@analytics-upgrade-test:5432/analytics_db \
  -e TEST_ANALYTICS_DATABASE_URL=postgresql://analytics_reader:isolated_test_reader@analytics-upgrade-test:5432/analytics_db \
  -e TEST_ALLOW_RESET=1 analytics-upgrade-test-runner pytest -q
docker cp backend/app analytics-upgrade-final-checks:/app/app
docker cp backend/tests analytics-upgrade-final-checks:/app/tests
docker start -a analytics-upgrade-final-checks
```

These passwords were disposable test credentials, not application secrets. See the root README for reusable local test-database setup.

Image build commands:

```bash
docker --config /tmp/analytics-docker-config build --target production -t analytics-upgrade-backend backend
docker --config /tmp/analytics-docker-config build --target test -t analytics-upgrade-test-runner backend
docker --config /tmp/analytics-docker-config build -t analytics-upgrade-frontend frontend
```

Compose verification used generated disposable credentials, the built images, a local provider URL, and an override removing published ports:

```bash
docker --config /tmp/analytics-docker-config compose \
  --env-file /tmp/analytics-compose-check.env -p analytics-upgrade-smoke \
  -f docker-compose.yml -f /tmp/analytics-compose-check.yml config --quiet
docker --config /tmp/analytics-docker-config compose \
  --env-file /tmp/analytics-compose-check.env -p analytics-upgrade-smoke \
  -f docker-compose.yml -f /tmp/analytics-compose-check.yml up -d --no-build
docker --config /tmp/analytics-docker-config compose \
  --env-file /tmp/analytics-compose-check.env -p analytics-upgrade-smoke \
  -f docker-compose.yml -f /tmp/analytics-compose-check.yml exec -T backend python -m app.scripts.seed
docker exec analytics-upgrade-smoke-backend-1 python /tmp/smoke.py
```

The temporary smoke client/provider and overrides are verification artifacts, not required application components. Database, backend and frontend reported healthy; the migration service exited successfully. A discovered initialization race was fixed by checking PostgreSQL readiness over TCP instead of its temporary initialization socket.

## Environment and remaining limits

- The host Docker credential helper referenced a Windows executable that could not run here. Builds used a temporary empty Docker client configuration; the user's configuration was not changed.
- Host port publication failed in this environment's Docker forwarding layer. Container-to-container HTTP verified the full reverse proxy; a published localhost endpoint was not verified here.
- Pre-existing Python cache directories had incompatible ownership. Compilation succeeded using a temporary cache prefix without changing ownership of existing files.
- Compatible npm security updates were applied. Five high-severity audit entries remain in Tailwind 3's development dependency chain for nested glob-pattern denial of service. Removing that chain requires a separate Tailwind major migration. These Node dependencies are absent from the Nginx runtime image.
- No live-provider accuracy, hosted deployment, or remote CI success is claimed. SQL population enforcement does not prove arbitrary generated joins/calculations or findings correct.
