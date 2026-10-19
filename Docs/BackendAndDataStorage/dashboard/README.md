# Dashboard

`GET /api/dashboard/summary` returns network flow, detection and alert counts for
a selected time range. Requires an access token belonging to an existing `user`
or `admin` account:

```http
GET /api/dashboard/summary?start_time=2026-01-01T00:00:00Z&end_time=2026-01-02T00:00:00Z
Authorization: Bearer <access_token>
```

## Request

| Query parameter | Required | Meaning |
| --- | --- | --- |
| `start_time` | Yes | Inclusive start, ISO 8601 timestamp with a timezone |
| `end_time` | Yes | Exclusive end, ISO 8601 timestamp with a timezone |

The range is `[start_time, end_time)`, with `start_time < end_time`. Equal or
reversed bounds are invalid. Both parameters must include a timezone: `Z` or an
explicit UTC offset, such as `+01:00`. Different offsets are compared as instants,
not as local clock times. Encode `+` as `%2B` when writing an offset directly in a URL.

Parameters are read from the URL; the endpoint has no request body. There is no
default range. Adjacent ranges can share a boundary without counting the same
record twice.

Example from PowerShell, after obtaining an access token through
[`POST /api/v1/auth/login`](../auth/README.md):

```powershell
$headers = @{ Authorization = "Bearer <access_token>" }
$uri = 'http://127.0.0.1:8000/api/dashboard/summary?start_time=2026-01-01T00:00:00Z&end_time=2026-01-02T00:00:00Z'
Invoke-RestMethod -Method Get -Uri $uri -Headers $headers
```

## Response

Status: `200 OK`.

```json
{
  "flow_count": 120,
  "detection_count": 8,
  "alert_count": 3
}
```

| Field | Counted table | Time column |
| --- | --- | --- |
| `flow_count` | `network_flows` | `ts_start` |
| `detection_count` | `detections` | `created_at` |
| `alert_count` | `alerts` | `created_at` |

All fields are nonnegative integers. A range containing no matching records
returns three zeros, even if the tables contain data outside that range.

Each table is counted independently. Ingestion timestamps do not determine the
range. Flows are counted as rows, including separate rows with the same `flow_id`
and different `ts_start` values. Detections without alerts count. All alert
statuses count, including acknowledged alerts; the related detection may have
been created outside the selected range.

## Errors

| Status | Cause | Response |
| --- | --- | --- |
| `401` | Missing, invalid or expired access token; refresh token used instead; user no longer exists | `{"detail": "Authentication failed"}` |
| `422` | Missing parameter, invalid timestamp, missing timezone, equal or reversed bounds | `{"detail": [...]}` with validation errors |
| `503` | Database operation failed | `{"detail": "Database storage unavailable"}` |

A `401` response includes `WWW-Authenticate: Bearer`. For example, equal bounds
produce this validation error:

```json
{
  "detail": [
    {
      "loc": ["query", "end_time"],
      "msg": "Value error, end_time must be after start_time",
      "type": "value_error"
    }
  ]
}
```

## Implementation

The controller receives a Pydantic request through `Query()` and creates
`GetDashboardSummaryHandler(session)` directly. The request validator checks the
time range; the controller maps it to `GetDashboardSummaryQuery`. Handlers and
request DTOs are not created through dependency injection.

Dependencies supply the database session, token verification and role checks.
The handler executes one `SELECT` containing three independent `COUNT(*)` scalar
subqueries. This avoids multiplying records through joins and gives all three
counts the same statement snapshot. The endpoint does not write or commit data.

The query model requires FastAPI 0.115 or newer, as declared in the API requirements.
Interactive contracts are available at `/docs` and `/openapi.json`.

## Tests

[Integration tests](../../../services/api/tests/integration/test_dashboard_summary.py)
exercise HTTP, authentication, the handler and an isolated TimescaleDB database
without mocks or dependency overrides. They cover both roles, empty results,
independent timestamps and counts, microsecond boundaries, adjacent ranges,
equivalent offsets, validation errors, query-only input, authentication failures
and the OpenAPI contract.

[Unit tests](../../../services/api/tests/unit/test_dashboard_summary_request.py)
exercise range validation without HTTP or a database: comparison across offsets,
a one-microsecond range, equal/reversed bounds and invalid start values.
SQL aggregation is verified by integration tests rather than a mocked session.

From `services/api`, with the environment activated:

```powershell
python -m pytest tests/unit/test_dashboard_summary_request.py -q
python -m pytest tests/integration/test_dashboard_summary.py -q
python -m pytest tests -q
```

Integration tests require Docker Desktop with Linux containers. Their database
is created and removed automatically; application data is not used.

[Architecture](../architecture/README.md) | [Endpoint plan](../endpoints.md) |
[Source code](../../../services/api/app/features/dashboard/) | [Test setup](../../../services/api/tests/README.md)
