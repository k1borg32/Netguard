# API endpoint plan

This list was restored from the [integration plan](../Architecture/Backend_Data_Storage/integration.md)
introduced in commit `12c9058` and updated to reflect the current implementation.
Checked items are implemented; unchecked items are planned.

Authentication uses the `/api/v1/auth` prefix; dashboard uses `/api/dashboard`.
Planned endpoints retain the `/api/...` paths from the original plan.

## Health

- [x] `GET /health/ping` — check that the API is running.

## Authentication

- [x] `POST /api/v1/auth/login` — authenticate a user and issue a token pair.
- [x] `POST /api/v1/auth/register` — create a user account as an administrator.
- [x] `POST /api/v1/auth/refresh` — refresh and rotate tokens.
- [x] `POST /api/v1/auth/logout` — invalidate the refresh token session.
- [x] `GET /api/v1/auth/me` — retrieve the current user's details.

## Dashboard

- [x] `GET /api/dashboard/summary` — retrieve flow, detection and alert counts within a selected time range.

Requires a Bearer access token belonging to an existing user (user or admin).
Required query parameters `start_time` and `end_time` are ISO 8601 timestamps with
a timezone, for example `2026-01-01T00:00:00Z`. The range is `[start_time, end_time)`;
`start_time` must be earlier than `end_time`. Invalid or missing parameters return 422;
missing or invalid authentication returns 401.

Example: `GET /api/dashboard/summary?start_time=2026-01-01T00:00:00Z&end_time=2026-01-02T00:00:00Z`

```json
{"flow_count": 120, "detection_count": 8, "alert_count": 3}
```

Flows are counted by `network_flows.ts_start`; detections and alerts by their own
`created_at`. All alert statuses count, regardless of the related detection's creation
time. Ranges containing no records return zero counts. The three independent counts use one SQL statement.

[Dashboard documentation and tests](dashboard/README.md).

## Alerts

- [ ] `GET /api/alerts` — list alerts with filtering, sorting and pagination.
- [ ] `GET /api/alerts/{id}` — retrieve an alert and its related detection.
- [ ] `PATCH /api/alerts/{id}/acknowledge` — mark an alert as acknowledged.

## Detections

- [ ] `GET /api/detections` — list detected anomalies with pagination.
- [ ] `GET /api/detections/{id}` — retrieve detection details: type, method, confidence and explanation.
- [ ] `GET /api/detections/{id}/flows` — retrieve flows associated with a detection.

## Network flows

- [ ] `GET /api/flows` — list flows with filtering, sorting and pagination.
- [ ] `GET /api/flows/{flowId}?tsStart={timestamp}` — retrieve a flow by its identifier and start time.

## Detection configurations

- [ ] `GET /api/detection-configurations` — list detection configurations.
- [ ] `GET /api/detection-configurations/{id}` — retrieve configuration details.
- [ ] `POST /api/detection-configurations` — create a configuration.
- [ ] `PATCH /api/detection-configurations/{id}` — update a configuration.
- [ ] `PUT /api/detection-configurations/{id}/activate` — set a configuration as active.

## Common requirements

- JSON over HTTP, with contracts documented in OpenAPI.
- Token-based authentication and authorization for protected operations.
- Filtering by time range, severity, detection type, IP address, protocol and alert status where applicable.
- Pagination for lists and sorting by timestamp.
- Standard HTTP status codes and consistent error responses.
