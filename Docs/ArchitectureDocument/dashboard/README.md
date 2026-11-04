# Architecture Document - Monitoring Dashboard (M4)

> Owner: Daniyar (M4, Frontend & Visualization)
> Covers: `services/dashboard/`, the screens of the web UI, how the UI gets its data from the REST API,
> login, and what the UI still needs from the API (F12, F13, F16, F17, UC-02 to UC-09).

## 1. Responsibility

The dashboard is the only part of NetGuard a user sees. It shows live traffic statistics, trend charts, alerts and
detection details with their evidence, the stored history, flows, and lets an administrator change detection
thresholds.

It is a static single-page application (SPA). It has no database and no business logic of its own: every number on
the screen comes from the REST API (`services/api`, M3). It never talks to the broker or the database directly.

## 2. Screens

Wireframes are in [`wireframes/`](wireframes/). They are low fidelity: layout and content, not the final look.

| # | Screen | Shows | Requirements | API it uses |
|---|---|---|---|---|
| 1 | Login | username + password form | NFR06 | `POST /auth/login` |
| 2 | Overview | stat cards (flows, flows/s, detections, open alerts), traffic trend, detections over time by severity, detections by type, latest detections | F12, UC-06 | `GET /dashboard/summary`, `GET /dashboard/timeseries`, `GET /alerts`, `GET /detections` |
| 3 | Alerts | alert list with filters (time, status, severity, type, source/destination IP), paging, acknowledge | F13, F17, UC-02, UC-05, UC-09 | `GET /alerts`, `PATCH /alerts/{id}/acknowledge` |
| 4 | Alert details | type, severity, status, confidence, window, explanation, feature values, contributing flows, trace IDs | F09, F15, UC-03 | `GET /alerts/{id}`, `GET /detections/{id}/flows` |
| 5 | History | all stored detections (also the ones without an alert), filters, detections-per-hour chart | F13, UC-04 | `GET /detections` |
| 6 | Flows | normalised flows with filters and paging | F11, UC-08 | `GET /flows`, `GET /flows/{flowId}` |
| 7 | Settings | detection configurations (edit and activate, admin only) | F16, UC-07 | `/detection-configurations` |

All API paths in this document are relative to `/api/v1`.

Every screen except Login has the same frame: top bar with API/DB health and the user menu,
and a side menu with the five pages. Users without the admin role see Settings read-only; the API enforces this
anyway, the UI only hides buttons that would fail.

| | |
|---|---|
| ![Login](wireframes/01-login.svg) | ![Overview](wireframes/02-overview.svg) |
| ![Alerts](wireframes/03-alerts.svg) | ![Alert details](wireframes/04-alert-details.svg) |
| ![History](wireframes/05-history.svg) | ![Flows](wireframes/06-flows.svg) |
| ![Settings](wireframes/07-settings.svg) | |

## 3. Technology

| Concern | Choice | Why |
|---|---|---|
| UI framework | React 19 + TypeScript | Required by the team plan. TypeScript lets us write the API response types once and catch contract changes at build time. |
| Build tool | Vite | Fast dev server with a proxy to the API, produces plain static files for nginx. |
| Routing | React Router | One URL per screen, so alert details can be linked and bookmarked (`/alerts/<id>`). |
| Server data | TanStack Query | Polling (`refetchInterval`), caching, retries, pauses when the browser tab is hidden. Replaces a lot of hand-written `useEffect` code. |
| Charts | Recharts | See 3.1. |
| Styling | Plain CSS with CSS variables | No UI kit: small bundle, nothing to learn, enough for tables, forms and cards. |
| Tests | Vitest + React Testing Library | Component tests (test plan section 8, M4). Same config as Vite. |
| End-to-end | Playwright | ST-02 to ST-05 and SEC-08 together with M5 in week 7 (issue #14). |

### 3.1 Chart library: Recharts

We need line/area charts over time, stacked bars by severity and horizontal bars by type, with tooltips and legends.
The API returns pre-aggregated buckets, so one chart has at most a few hundred points.

| Option | For | Against |
|---|---|---|
| **Recharts** (chosen) | Charts are normal React components, so they re-render from the same query data as the tables. SVG output: sharp, easy to test, text is escaped. Has every chart type we need. | Slower than canvas with tens of thousands of points, which we never draw (the API aggregates). |
| Chart.js | Fast canvas rendering, popular | Imperative API; needs a React wrapper; canvas content is not visible to component tests. |
| Apache ECharts | Very powerful, fast | Large bundle, many features we don't need. |
| D3 | Full control | Low level; every axis and tooltip by hand; too slow to build in our timeline. |
| Grafana | Ready-made dashboards | A separate tool, not our application; no alert acknowledge; the spec asks for our own dashboard. |

## 4. How the dashboard gets its data

### 4.1 Deployment and request path

```mermaid
flowchart LR
  B[Browser] -->|"GET / (HTML, JS, CSS)"| N[nginx<br/>dashboard container<br/>127.0.0.1:3000]
  B -->|"/api/v1/... JSON + Bearer token"| N
  N -->|"proxy /api/ unchanged"| A[FastAPI<br/>api:8000]
  A --> D[(TimescaleDB)]
```

- The React app is built in a multi-stage Docker image (`node` stage runs `npm ci && npm run build`, the `nginx`
  stage serves `dist/`). `docker compose up -d --build` keeps working as the one start command (NFR05).
- nginx serves the static files and proxies `/api/` to the API container **without changing the path**, so the
  browser calls `/api/v1/alerts` and the API receives `/api/v1/alerts`. The API health check is exposed as
  `/api/health`. Same origin for UI and API: no CORS configuration needed.
- Unknown paths fall back to `index.html` (`try_files`), so a page reload on `/alerts/<id>` works.
- nginx adds security headers: a Content-Security-Policy that only allows our own scripts, `X-Content-Type-Options`,
  `Referrer-Policy`.
- During development `npm run dev` starts Vite on port 5173 and proxies `/api` to `http://localhost:8000`, so the UI
  can be developed against the normal compose stack with hot reload.

### 4.2 Polling, not WebSockets (for now)

All data is fetched with REST calls. Screens that show live data refetch on a timer:

| Screen | Refresh |
|---|---|
| Overview (cards, charts, latest alerts) | every 5 s |
| Alerts list | every 5 s |
| Alert details | every 10 s (status may be changed by another user) |
| Top bar (health) | every 10 s |
| History, Flows, Settings | on load and when filters change, plus a manual refresh button |

Polling stops while the browser tab is hidden and restarts with an immediate refetch when it becomes visible again
(TanStack Query default). After an acknowledge, the alert queries are invalidated, so the change shows at once.

Why not WebSockets or Server-Sent Events now:

- Nothing pushes data to the API: the persister writes to the database and the API only reads it. A push channel
  would need a new source (Postgres `LISTEN/NOTIFY` or a consumer of the `detections` topic inside the API).
- It needs authentication on a long-lived connection, nginx upgrade settings and reconnect logic.
- A 5 s delay is fine for a human operator. Detection itself (NFR02) is measured in the pipeline, not in the UI.
- The Management API integration plan already lists real-time updates as out of MVP scope.

If there is time after week 7, an SSE endpoint `GET /stream/alerts` can replace the 5 s polling of the alert list;
the screens would not change.

Load: one open dashboard makes about 4 requests per 5 s. The k6 API load test (PT-05) polls the alert list every
2 s per virtual user, which is more than the dashboard does, so it is a safe upper bound.

### 4.3 Time ranges

The user picks a range (last 5 min / 15 min / 1 h / 6 h / 24 h). The UI sends `start_time` and
`end_time` as ISO 8601 in UTC (`2026-10-20T12:00:00Z`), which the summary and alert endpoints require.
Times are shown in the browser's local time zone.

## 5. Login and tokens

Authentication is Jakub's JWT module (`/auth/*`, see [Authentication](../../ManagementAPI/auth/README.md)):
access token valid for 15 min, refresh token for 7 days, refresh rotates the pair, tokens are sent in the
`Authorization: Bearer` header.

```mermaid
sequenceDiagram
  actor U as User
  participant UI as Dashboard (browser)
  participant API as API /api/v1
  U->>UI: username + password
  UI->>API: POST /auth/login
  API-->>UI: access_token, refresh_token
  UI->>API: GET /auth/me (Bearer access)
  API-->>UI: user_id, username, role
  loop every screen
    UI->>API: GET /alerts ... (Bearer access)
    API-->>UI: 200 JSON
  end
  Note over UI,API: after 15 min the access token expires
  UI->>API: GET /alerts (expired access)
  API-->>UI: 401
  UI->>API: POST /auth/refresh (Bearer refresh)
  API-->>UI: new access + refresh (old refresh now invalid)
  UI->>API: GET /alerts again (new access)
  U->>UI: Log out
  UI->>API: POST /auth/logout (Bearer refresh)
```

Rules in the UI:

- The **access token is kept in memory only**. The **refresh token is kept in `sessionStorage`**, so a page reload
  does not log the user out, and closing the tab does.
- On a `401` the API client calls `/auth/refresh` **once** and repeats the request. Several requests that fail at the
  same time share one refresh call; this matters because refresh rotates the token, and a second parallel refresh
  with the old token would get `401` and log the user out.
- If refresh fails, the UI clears the tokens and shows the login page with "session expired".
- The role from `/auth/me` decides which buttons are shown (admin: edit configuration).
  This is only convenience: the API checks the role on every request (NFR06).
- No self-registration in the UI: accounts are created by an administrator (`POST /auth/register`).
  The first administrator is created with `docker compose exec api python -m app.infrastructure.bootstrap_admin`.

Known limitation: a refresh token in `sessionStorage` can be read by an XSS bug. We reduce that risk with React's
escaping (we never use `dangerouslySetInnerHTML`, SEC-08) and the CSP header. An `HttpOnly` cookie for the refresh
token would be safer but needs API changes; we can revisit it in week 8.

## 6. API review from the UI side

I checked the [Management API integration plan](../ManagementAPI/integration.md), the
[endpoint list](../../ManagementAPI/endpoints.md) and the current code in `services/api` against the screens
in section 2.

| Screen | Endpoints | Enough? |
|---|---|---|
| Login, user menu | `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me` | Yes. |
| Overview, cards | `GET /dashboard/summary`, `GET /alerts?status=NEW` | Yes. The open-alert count comes from the `total` of the alert list. |
| Overview, charts | `GET /dashboard/timeseries`, `GET /detections` | Yes. The breakdown by type is counted in the UI from the latest 500 detections. |
| Alerts list | `GET /alerts` | Yes. Filters, paging and the detection fields for the table (G3). |
| Alert details | `GET /alerts/{id}`, `PATCH /alerts/{id}/acknowledge`, `GET /detections/{id}/flows` | Yes. |
| History | `GET /detections` | Yes. |
| Flows | `GET /flows`, `GET /flows/{flowId}` | Yes. |
| Settings, thresholds | `/detection-configurations` | Endpoints exist; see G8. |
| Top bar | `GET /health` | Yes. |

### 6.1 Gaps: status

The review was done in week 2. State after PR #50 and the detection engine (#62):

| Gap | What | State |
|---|---|---|
| G1 | Time-series endpoint for the trend charts | Done, see below |
| G2 | Open alerts and counts by type and severity in the summary | Not needed for now: the UI gets them from `GET /alerts` and `GET /detections` |
| G3 | Detection fields in the alert list items | Done, see below |
| G4 | Something has to create alerts | Done: the engine decides (`alerts` in `config/detection.yaml`: MEDIUM and above, `unknown` from HIGH, one alert per type/source/destination per 5 min) and the persister writes the alert with the detection |
| G5 | Filters and paging on `GET /detections` | Done |
| G6 | Evidence flows of a detection | Done: `GET /detections/{id}/flows` finds them by the detection's `trace_ids`, so it returns a sample |
| G7 | Filters on `GET /flows` | Done |
| G8 | Detection configuration form | Endpoints done, see below |
| G9 | Simulator control | Dropped: the supervisors removed the simulator from the requirements in week 3 |
| G10 | System metrics (instances, consumer lag, p95 latency) | Open, nice to have |

**G1 - Time-series endpoint for the trend charts (implemented for F12, ST-05).**

```http
GET /api/v1/dashboard/timeseries?start_time=2026-10-20T12:00:00Z&end_time=2026-10-20T12:15:00Z&interval=1m
```

```json
{
  "start_time": "2026-10-20T12:00:00Z",
  "end_time": "2026-10-20T12:15:00Z",
  "interval": "1m",
  "data": [
    {
      "timestamp": "2026-10-20T12:00:00Z",
      "flows_count": 12034,
      "detections_count": 3,
      "detections_by_severity": {"LOW": 1, "MEDIUM": 0, "HIGH": 2, "CRITICAL": 0}
    }
  ]
}
```

Intervals are `10s`, `30s`, `1m`, `5m`, `15m`, `1h` and `1d` (default `1h`).
The defaults cover the last 24 hours; ranges are limited to 366 days and 2000 UTC-aligned
buckets. Empty buckets include zero counts for each severity. Counts are aggregated in
one SQL statement over `[start_time, end_time)`; the four severity counts sum to
`detections_count`. The earlier proposal's per-bucket `packets` and `bytes` are not part of the response. The
"Flows/s" card can use `flows_count` divided by the bucket length of the last full bucket. A 15-minute live chart
can use `10s`, `30s` or `1m` buckets.

**G3 - Detection fields in the alert list (implemented).** `GET /alerts` items include the alert fields and a nested
`detection` summary (`type`, `severity`, `confidence`, `src_ip`, `dst_ip`, `protocol`) from the existing join, avoiding
an additional request per row. Nice to have: `acknowledged_by` (username),
the ERD has the Users - Alerts relation but the `alerts` table has no column for it yet.

**G8 - Detection configuration form.** The [configuration API](../../ManagementAPI/detection-configurations/README.md)
is implemented. `parameters` is free JSONB, so the UI shows one input per key with its current value
(numbers as number fields). `PATCH` replaces the whole supplied `parameters` object; omitted fields are unchanged.
Send all parameter keys to retain them. Invalid values return 422 with field locations. Writes are admin only;
reads require an access token. New definitions are inactive, and `PUT /api/v1/detection-configurations/{id}/activate`
enables the target without disabling other definitions. The current processor still reads YAML at startup;
persisting or activating a database definition does not reload it.

**Other notes for the API:**

- Rate limiting (NFR06, SEC-07): one dashboard tab makes about 4 requests per 5 s; the limit should allow a few
  tabs per user.
- Keep error bodies as they are now (`{"detail": ...}`), the UI shows `detail` when it is a string and maps
  validation errors to form fields.

## 7. Code structure

```
services/dashboard/
  Dockerfile            multi-stage: node build -> nginx
  nginx.conf            static files, /api proxy, SPA fallback, security headers
  package.json
  vite.config.ts        dev proxy /api -> localhost:8000, Vitest config
  src/
    main.tsx            React root, QueryClient, Router
    App.tsx             routes and the shared layout
    api/                fetch client (tokens, refresh, errors) + one file per resource with its types
    auth/               AuthProvider, login page, route guard
    components/         Layout, StatCard, SeverityBadge, tables, charts
    pages/              Overview, Alerts, AlertDetails, History, Flows, Settings
    lib/                time ranges and formatting helpers
```

Rules: API types in `src/api/` mirror the Pydantic responses; components never call `fetch` directly; all text from
the API is rendered as text (no HTML), which is what SEC-08 checks.

## 8. Testing

- **Component tests** (Vitest + Testing Library, `npm test`): API client refresh logic, login form, severity badge,
  alert table rendering, filter to query-string mapping, time-range helpers. Run in CI next to the Python tests.
- **End-to-end** (Playwright, week 7 with M5, issue #14): ST-02 attack from an imported file visible on the dashboard,
  ST-03 PCAP import visible, ST-04 history filters, ST-05 live statistics and charts update, SEC-08 HTML in a detection
  field shown as text.
- **Security**: `npm audit` in the week 9 scans (issue #17), ZAP baseline against the dashboard (SEC-12).

## 9. Plan

The dashboard part of the [work schedule](../../WorkSchedule/README.md):

| Week | Dashboard work | State |
|---|---|---|
| 2 | this section, wireframes, API review, React app in `services/dashboard`, Docker build into nginx, login | done |
| 3-4 | Overview with cards and trend charts (#34) | in review |
| 5 | Alerts list with filters, alert details with evidence, acknowledge (#35) | in review |
| 6 | History and Flows screens (#36) | planned |
| 7 | Settings: detection thresholds (#37), Playwright end-to-end tests with M5 (#14) | planned |
| 8 | Loading, error and empty states, accessibility, check under API load (#38) | planned |
| 9-10 | `npm audit`, screenshots for the test report and the demo, bug fixes (#39) | planned |

## 10. Open questions

- Flows are counted by their own start time (`ts_start`), while detections get the current time. A file imported with
  its original timestamps therefore shows detections but no traffic in "last hour"; the Overview says so when a range
  has no flows. Importing with `REPLAY_SPEED` (M1) moves the flows to the present.
- Detection configurations live in the database, but the engine reads `config/detection.yaml` at start-up. The Settings
  screen needs runtime changes to reach the engine (week 6, M2, F16).
- UC-01 "Import PCAP files" is listed for the End User. The importer (M1) is a command-line tool for now; uploading a
  PCAP from the dashboard is not planned unless we decide otherwise.
