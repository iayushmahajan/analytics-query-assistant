# Analytics workspace frontend

React + strict TypeScript + Vite + Tailwind + Recharts. See the [project README](../README.md) for architecture, API contracts, configuration and database setup.

```bash
npm ci
npm run dev
```

The development server proxies `/api` to `http://localhost:8000`. `VITE_API_BASE_URL` overrides that path for separate hosting and is embedded at build time.

```bash
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The production Docker image builds static assets and serves them with Nginx, proxying `/api` to the backend container. Browser tests use mocked API responses and do not consume model credits.
