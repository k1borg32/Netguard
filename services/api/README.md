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

`GET /api/v1/dashboard/timeseries` returns unified flow and detection counts in
UTC-aligned time buckets. It requires the same Bearer access token as summary.
Optional query parameters are `from`, `to` (ISO 8601 timestamps with timezones)
and `interval` (`5m`, `15m`, `1h`, `1d`; default `1h`). Offsets are normalized to UTC.
`to` defaults to now; `from` defaults to 24 hours before the resolved `to`.
With only `from`, the range ends now. Equal/reversed bounds, invalid timestamps,
unsupported intervals, ranges over 366 days and results over 2000 buckets return
`422`. The bucket limit includes partial buckets.

```http
GET /api/v1/dashboard/timeseries?from=2026-10-20T00:00:00Z&to=2026-10-20T03:00:00Z&interval=1h
Authorization: Bearer <access_token>
```

Example response for an empty range:

```json
{
  "from": "2026-10-20T00:00:00Z",
  "to": "2026-10-20T03:00:00Z",
  "interval": "1h",
  "data": [
    {"timestamp": "2026-10-20T00:00:00Z", "flows_count": 0, "detections_count": 0},
    {"timestamp": "2026-10-20T01:00:00Z", "flows_count": 0, "detections_count": 0},
    {"timestamp": "2026-10-20T02:00:00Z", "flows_count": 0, "detections_count": 0}
  ]
}
```

The range is `[from, to)`, filtering flows by `ts_start` and detections by
`created_at`. Buckets are ordered, empty buckets contain zeros, and partial
buckets only count records inside the requested range. A bucket timestamp marks
its UTC-aligned start, which may precede `from`; a rolling 24-hour range can
therefore intersect 25 hourly buckets. Response bounds preserve the exact range
and all timestamps are serialized in UTC with `Z`.

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
