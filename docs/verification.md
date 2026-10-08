# Verification record

Verified locally on 8 October 2026. The populated `.env` was not read into output or modified.

| Check | Result |
| --- | --- |
| Backend Ruff | Passed |
| Complete backend suite on PostgreSQL 16 | **89 passed** against a disposable database |
| Frontend Vitest | **14 passed** |
| Frontend ESLint and TypeScript production build | Passed |
| Playwright Chromium desktop/mobile workflows | **2 passed** |
| Production dependency audit | **0 vulnerabilities** |
| Docker Compose migration and service startup | Passed |
| Live Eurostat import | **14,955 observations**, January 2015–August 2026 |
| Live dashboard API | Passed through the Nginx `/api` proxy |
| Live configured-provider query | Passed: typed plan → validated SQL → PostgreSQL → deterministic findings |

The live query asked for Germany's latest total-retail index. It returned August 2026 at **99.90 (2021=100)** and correctly explained that this is **0.10 index points below** the reference level. Provider generation took under one second in the observed run; SQL execution took eight milliseconds. These timings are environment-specific.

The test suite covers malformed provider output, provider errors, typed-plan gating, clarification, metric-policy mismatches, unsafe and unknown SQL, row/byte/time limits, result-context bounds, import dimension drift, invalid values, missing periods, deterministic derived metrics, anomaly thresholds, migration/model parity, retired-table removal, least-privilege database roles, history restoration, auto-scroll, unit formatting, CSV injection safety, charts, and mobile layout.

The Eurostat importer validated the current JSON-stat structure and atomically loaded 28 geographies and four categories. The latest country ranking contained 25 members with a reported value for the same latest month; missing source cells remain visible in data-quality metadata rather than being imputed.

One upstream Starlette/AnyIO deprecation warning appears in backend tests. The full frontend install reports advisories in development tooling, while `npm audit --omit=dev` reports zero vulnerabilities in production dependencies.
