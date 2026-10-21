# API endpoint plan

This list was restored from the [integration plan](../Architecture/Backend_Data_Storage/integration.md)
introduced in commit `12c9058` and updated to reflect the current implementation.
Checked items are implemented; unchecked items are planned.

All endpoints use the `/api/v1` prefix, the planned ones too.

## Health

- [x] `GET /health` - check the API and its database connection (used by the Compose healthcheck).
- [x] `GET /health/ping` - check that the API is running.

## Authentication

- [x] `POST /api/v1/auth/login` - authenticate a user and issue a token pair.
- [x] `POST /api/v1/auth/register` - create a user account as an administrator.
- [x] `POST /api/v1/auth/refresh` - refresh and rotate tokens.
- [x] `POST /api/v1/auth/logout` - invalidate the refresh token session.
- [x] `GET /api/v1/auth/me` - retrieve the current user's details.

## Dashboard

- [x] `GET /api/v1/dashboard/summary` - retrieve flow, detection and alert counts within a selected time range.

Requires a Bearer access token belonging to an existing user (user or admin).
Required query parameters `start_time` and `end_time` are ISO 8601 timestamps with
a timezone, for example `2026-01-01T00:00:00Z`. The range is `[start_time, end_time)`;
`start_time` must be earlier than `end_time`. Invalid or missing parameters return 422;
missing or invalid authentication returns 401.

Example: `GET /api/v1/dashboard/summary?start_time=2026-01-01T00:00:00Z&end_time=2026-01-02T00:00:00Z`

```json
{"flow_count": 120, "detection_count": 8, "alert_count": 3}
```

Flows are counted by `network_flows.ts_start`; detections and alerts by their own
`created_at`. All alert statuses count, regardless of the related detection's creation
time. Ranges containing no records return zero counts. The three independent counts use one SQL statement.

[Dashboard documentation and tests](dashboard/README.md).

- [x] `GET /api/v1/dashboard/timeseries` - retrieve shared UTC buckets containing flow and detection counts.

Requires the same Bearer access token as summary. Optional query parameters:
`from` (inclusive), `to` (exclusive), and `interval` (`5m`, `15m`, `1h`, `1d`).
Defaults to the last 24 hours and `1h`. Empty buckets contain zeros; results are
chronological. Counts use `network_flows.ts_start` and `detections.created_at`.
Bounds are ISO 8601 timestamps with timezones and responses use UTC. Queries may
span at most 366 days and intersect at most 2000 buckets; invalid input returns 422.

Example: `GET /api/v1/dashboard/timeseries?from=2026-10-20T00:00:00Z&to=2026-10-20T03:00:00Z&interval=1h`

[Time-series contract](dashboard/README.md#time-series).

## Alerts

- [ ] `GET /api/v1/alerts` - list alerts with filtering, sorting and pagination.
- [ ] `GET /api/v1/alerts/{id}` - retrieve an alert and its related detection.
- [ ] `PATCH /api/v1/alerts/{id}/acknowledge` - mark an alert as acknowledged.

## Detections

- [x] `GET /api/v1/detections` - filter, sort and paginate detections (`page_size` 1-500; legacy `limit` alias).
  Public for now; newest first by default.
- [x] `GET /api/v1/detections/{id}` - retrieve detection details: type, method, confidence and explanation.
- [x] `GET /api/v1/detections/{id}/flows` - paginate retained flows matching the detection's trace-ID sample.

[Detection contracts, tests and PlantUML sequences](detections/README.md).

## Network flows

- [ ] `GET /api/v1/flows` - list flows with filtering, sorting and pagination.
- [ ] `GET /api/v1/flows/{flowId}?tsStart={timestamp}` - retrieve a flow by its identifier and start time.

## Detection configurations

- [ ] `GET /api/v1/detection-configurations` - list detection configurations.
- [ ] `GET /api/v1/detection-configurations/{id}` - retrieve configuration details.
- [ ] `POST /api/v1/detection-configurations` - create a configuration.
- [ ] `PATCH /api/v1/detection-configurations/{id}` - update a configuration.
- [ ] `PUT /api/v1/detection-configurations/{id}/activate` - set a configuration as active.

## Common requirements

- JSON over HTTP, with contracts documented in OpenAPI.
- Token-based authentication and authorization for protected operations.
- Filtering by time range, severity, detection type, IP address, protocol and alert status where applicable.
- Pagination for lists and sorting by timestamp.
- Standard HTTP status codes and consistent error responses.
