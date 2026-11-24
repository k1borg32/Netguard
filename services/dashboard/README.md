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

## End-to-end tests (Playwright)

They run in a real browser against the running stack (test plan ST-02 to ST-05, SEC-08), in CI as the `e2e` job.

```bash
docker compose up -d                  # in the repository root, the whole stack
npx playwright install chromium       # once
npx playwright test                   # here, in services/dashboard
```

`e2e/global-setup.ts` runs first: it creates the test account `e2e-admin` with a new random password and imports a
port scan from a new attacker address, so every run has its own alert. A test signs in with `signIn(page)` and finds
that alert with `attacker()` (both in `e2e/helpers.ts`). Test files are named `*.e2e.ts`, so Vitest leaves them alone.
On Windows run it from a terminal that shows the drive as `D:` (see Troubleshooting in the main README).

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
