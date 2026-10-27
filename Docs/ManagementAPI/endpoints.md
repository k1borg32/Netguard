# API endpoint plan

This list was restored from the [integration plan](../ArchitectureDocument/ManagementAPI/integration.md)
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

- [x] `GET /api/v1/detections` - latest detections, newest first (`limit` 1-500). No pagination yet;
  no token needed until the dashboard has a login.
- [x] `GET /api/v1/detections/{id}` - retrieve detection details: type, method, confidence and explanation.
- [x] `GET /api/v1/detections/{id}/flows` - retrieve flows associated with a detection.

## Network flows

- [x] `GET /api/v1/flows` - list flows with filtering, sorting and pagination.
- [x] `GET /api/v1/flows/{flowId}?tsStart={timestamp}` - retrieve a flow by its identifier and start time.

Both endpoints require a Bearer access token belonging to an existing user (user or admin).

The list accepts optional `start_time` (inclusive) and `end_time` (exclusive) filters on
`ts_start`, as ISO 8601 timestamps with a timezone. When both are present,
`start_time` must precede `end_time`. Other optional filters are `src_ip`, `dst_ip`
(IPv4 or IPv6 addresses), `src_port`, `dst_port` (0-65535), and `protocol`
(an exact, case-sensitive match). Filters are combined with AND.

`sort_order=asc|desc` defaults to `desc` and orders by `ts_start`, then `flow_id`
in the same direction for deterministic pagination. `page` starts at 1 (default 1);
`page_size` is 1-100 (default 50). The response contains `items`, `total`, `page`
and `page_size`. `total` counts all matching flows, including on empty or
out-of-range pages; items and total use one database snapshot.

Example: `GET /api/v1/flows?start_time=2026-01-01T00:00:00Z&end_time=2026-01-02T00:00:00Z&protocol=TCP&sort_order=desc&page=1&page_size=50`

The detail endpoint requires both a UUID `flowId` and a timezone-aware `tsStart`
query parameter because flows have a composite primary key. Equivalent timezone
offsets identify the same instant. If no flow matches the pair, the endpoint returns 404; malformed UUIDs,
missing/invalid timestamps, invalid list filters or pagination return 422.
Missing or invalid authentication returns 401; database failures return 503.

Example: `GET /api/v1/flows/00000000-0000-0000-0000-000000000001?tsStart=2026-01-01T00:00:00Z`

Both endpoints return the same flow fields: `flow_id`, `ts_start`, `trace_id`,
`ingested_at`, `duration_ms`, `src_ip`, `dst_ip`, `src_port`, `dst_port`, `protocol`,
`packets`, `bytes`, `tcp_flags`, `source` and `label`. All fields except the composite
key can be `null`. Timestamps use ISO 8601 with a timezone; IP addresses are strings.

## Detection configurations

- [x] `GET /api/v1/detection-configurations` - list detection configurations.
- [x] `GET /api/v1/detection-configurations/{id}` - retrieve configuration details.
- [x] `POST /api/v1/detection-configurations` - create a configuration.
- [x] `PATCH /api/v1/detection-configurations/{id}` - update a configuration.
- [x] `PUT /api/v1/detection-configurations/{id}/activate` - set a configuration as active.

See [Detection configurations](detection-configurations/README.md) for authentication,
pagination, JSON replacement semantics, activation and the processor integration limitation.

## Common requirements

- JSON over HTTP, with contracts documented in OpenAPI.
- Token-based authentication and authorization for protected operations.
- Filtering by time range, severity, detection type, IP address, protocol and alert status where applicable.
- Pagination for lists and sorting by timestamp.
- Standard HTTP status codes and consistent error responses.
