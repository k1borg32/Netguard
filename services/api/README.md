# NetGuard API

- [API endpoint plan](../../Docs/BackendAndDataStorage/endpoints.md)
- [Architecture](../../Docs/BackendAndDataStorage/architecture/README.md)
- [Authentication](../../Docs/BackendAndDataStorage/auth/README.md)
- [Dashboard](../../Docs/BackendAndDataStorage/dashboard/README.md)

## Run

Install `requirements.txt`. Set `DATABASE_URL` and `JWT_SECRET` in the environment
or the repository's `.env`. From `services/api`, with the environment activated:

```powershell
python -m app.app
```

This entry point configures the Windows event loop required by psycopg async.
The Linux container uses `uvicorn app.app:app --host 0.0.0.0 --port 8000`.

Open `/docs` for interactive documentation and `/openapi.json` for the schema.
`GET /health/ping` returns `{"status": "ok"}` without accessing the database.
`GET /health` also checks the database and returns `{"status": "ok", "db": "ok"}`; the Compose
healthcheck uses it.

`GET /api/v1/dashboard/summary` returns `flow_count`, `detection_count` and `alert_count`.
Send a Bearer access token and required `start_time` / `end_time` query parameters
as ISO 8601 timestamps with timezones. The start is inclusive, the end exclusive;
the start must precede the end. See the endpoint plan for a request example.

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
