# NetGuard Management API

- [API endpoint plan](../../Docs/ManagementAPI/endpoints.md)
- [Architecture](../../Docs/ManagementAPI/architecture/README.md)
- [Authentication](../../Docs/ManagementAPI/auth/README.md)
- [Dashboard](../../Docs/ManagementAPI/dashboard/README.md)
- [Detections](../../Docs/ManagementAPI/detections/README.md)
- [Detection configurations](../../Docs/ManagementAPI/detection-configurations/README.md)

## Run

Install `requirements.txt`. Set `DATABASE_URL` and `JWT_SECRET` in the environment
or the repository's `.env`. To load `.env` explicitly, run from `services/api`
with the environment activated:

```powershell
python run.py
```

Use `python -m app.app` when the variables are already exported; it configures the
Windows event loop required by psycopg async. Settings do not discover `.env`
automatically. Missing settings fail at startup without exposing their values.
The Linux container uses `uvicorn app.app:app --host 0.0.0.0 --port 8000`.

Open `/docs` for interactive documentation and `/openapi.json` for the schema.
`GET /health/ping` returns `{"status": "ok"}` without accessing the database.
`GET /health` also checks the database and returns `{"status": "ok", "db": "ok"}`; the Compose
healthcheck uses it. An unavailable database returns HTTP 503 with degraded status.

`GET /api/v1/dashboard/summary` returns `flow_count`, `detection_count` and `alert_count`.
Send a Bearer access token and required `start_time` / `end_time` query parameters
as ISO 8601 timestamps with timezones. The start is inclusive, the end exclusive;
the start must precede the end. See the endpoint plan for a request example.

`GET /api/v1/dashboard/timeseries` matches the dashboard contract: query parameters
`start_time`, `end_time` (timezone-aware ISO 8601) and `interval_s` (whole seconds,
1-86400). The default end is now in UTC; the default start is 24 hours before the
resolved end, and the default interval is 3600 seconds. The start is inclusive
and the end exclusive. Ranges must be positive, at most 366 days, and intersect
at most 500 buckets, including partial buckets. Invalid queries return `422`.

```http
GET /api/v1/dashboard/timeseries?start_time=2026-10-20T12:00:00Z&end_time=2026-10-20T12:15:00Z&interval_s=60
Authorization: Bearer <access_token>
```

Response shape (one example point shown):

```json
{
  "interval_s": 60,
  "points": [
    {
      "ts": "2026-10-20T12:00:00Z",
      "flows": 12034,
      "packets": 401223,
      "bytes": 88123456,
      "detections": {"LOW": 1, "MEDIUM": 0, "HIGH": 2, "CRITICAL": 0}
    }
  ]
}
```

Points are ordered by `ts`, aligned to Unix epoch in UTC, with empty buckets
filled with zeros. The first bucket may begin before `start_time`; partial
buckets only count records inside `[start_time, end_time)`. Flow counts and
packet/byte sums use `network_flows.ts_start`; detection counts use
`detections.created_at` and include all four severity levels. Missing packet
or byte values contribute zero. Timestamps are serialized with `Z`.
The UI can use 5, 15, 60 and 900 seconds for its 5 min, 15 min, 1 h and 24 h views.

Like other features, the controller constructs its handler directly; the handler
uses the injected request-scoped `AsyncSession`. One parameterized SQL statement
uses TimescaleDB `time_bucket()`, independent aggregates, `generate_series()` and
left joins. No schema changes, repository layer or additional dependencies are
required. Existing `401` authentication and `503` database errors apply.

See the [dashboard contract](../../Docs/ManagementAPI/dashboard/README.md) for both endpoints.

## Network flows

`GET /api/v1/flows` lists flows with optional time, IP address, port and protocol
filters. Use `sort_order=asc|desc`, `page` (default 1) and `page_size` (default 50,
maximum 100). Responses include `items`, `total`, `page` and `page_size`.

`GET /api/v1/flows/{flowId}?tsStart={timestamp}` retrieves a flow by its composite
key. `tsStart` is required and must include a timezone. Both routes require a
Bearer access token. See the [endpoint plan](../../Docs/ManagementAPI/endpoints.md#network-flows)
for the complete contract.

## First administrator

```powershell
# From services/api:
python -m app.infrastructure.bootstrap_admin

# Or from the repository root with the API container running:
docker compose exec api python -m app.infrastructure.bootstrap_admin
```

The command prompts for credentials and refuses to create a second administrator.

## Database

The API uses the existing schema; it does not run migrations.
New database volumes apply `db/init/001_schema.sql`.
Existing databases missing `auth_refresh_sessions` require its table and index definitions
from that file; do not rerun the entire bootstrap script on an existing database.

## Tests

Install `requirements-dev.txt`, then run `python -m pytest tests -q`.
Integration tests start an isolated TimescaleDB container and require Docker Desktop.
See [tests/README.md](tests/README.md) for details.
