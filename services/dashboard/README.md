# NetGuard dashboard

React + TypeScript single-page app, built with Vite and served by nginx in the `dashboard` container.
Design, screens and API needs: [architecture doc, dashboard section](../../Docs/ArchitectureDocument/dashboard/README.md).

## Run with the whole stack

```bash
docker compose up -d --build
docker compose exec api python -m app.infrastructure.bootstrap_admin   # once per DB volume: first admin user
```

Open http://localhost:3000 and sign in. nginx serves the app and forwards `/api/v1/...` to the API container
with the same path; `/api/health` goes to the API's `/health`.

## Develop with hot reload

Needs Node.js 24 (same as the Docker build). Start the stack as above (the API must run on port 8000), then:

```bash
cd services/dashboard
npm ci
npm run dev          # http://localhost:5173, /api is proxied to http://localhost:8000
```

Other API address: `API_URL=http://host:port npm run dev`.

## Checks

```bash
npm test             # component and unit tests (Vitest + Testing Library)
npm run lint         # oxlint
npm run build        # type check + production build into dist/
```

## Structure

| Path | What |
|---|---|
| `src/api/` | `client.ts` (tokens, refresh on 401, errors) and one file per API resource with its response types |
| `src/auth/` | login page, `AuthProvider`, route guard |
| `src/components/` | layout, cards, badges, charts |
| `src/pages/` | one component per screen |
| `src/lib/` | time ranges, formatting, chart bucketing |
| `nginx.conf` | static files, `/api` proxy, React Router fallback, security headers |

Rules: components never call `fetch` directly (use `src/api/`), and API text is always rendered as text, never as
HTML (`dangerouslySetInnerHTML` is not used; SEC-08).
