# Alerts

All three endpoints require a Bearer access token belonging to an existing
`user` or `admin`. Both roles can view and acknowledge alerts.

## List

`GET /api/alerts` returns `200 OK` with:

```json
{
  "items": [
    {
      "alert_id": "00000000-0000-0000-0000-000000000001",
      "detection_id": "00000000-0000-0000-0000-000000000002",
      "status": "NEW",
      "created_at": "2026-01-01T12:00:00Z",
      "acknowledged_at": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50,
  "total_pages": 1,
  "has_next": false,
  "has_previous": false
}
```

All query parameters are optional:

| Parameter | Meaning / default |
| --- | --- |
| `start_time` | Inclusive lower bound on the **alert's** `created_at`, ISO 8601 with timezone |
| `end_time` | Exclusive upper bound on the **alert's** `created_at`, ISO 8601 with timezone |
| `status` | `NEW` or `ACKNOWLEDGED` |
| `severity` | Related detection: `LOW`, `MEDIUM`, `HIGH` or `CRITICAL` |
| `detection_type` | Exact detection `type`, e.g. `port_scan` |
| `src_ip`, `dst_ip` | Exact IPv4 or IPv6 host addresses from the detection; CIDR filters are unsupported |
| `protocol` | Exact detection protocol, e.g. `TCP` |
| `sort_order` | `desc` (default) or `asc`, applied to `created_at`, then `alert_id` |
| `page` | One-based page number, default `1` |
| `page_size` | `1..100`, default `50` |

Filters combine with AND. Text filters are case-sensitive. When both time bounds
are supplied, `start_time < end_time` is required; different timezone offsets
are compared as instants. Either time bound can be used alone. No bounds means
all creation times. Encode `+` as `%2B` in timestamps written directly in a URL.

`total` counts all matching alerts before pagination. Empty lists and pages
beyond the last page return `items: []`, retaining the matching total.
`total_pages` is the matching total divided by `page_size`, rounded up. No
matching records means zero pages. `has_next` indicates that a later page exists;
`has_previous` indicates that earlier pages exist. Both are false for no results.
For requests beyond the last page, the requested `page` is retained and
`has_next` is false; `has_previous` remains true if matching pages exist.
The items and count are read in one SQL statement and share a database snapshot.
UUID breaks timestamp ties deterministically; offset pagination can still shift
between requests if matching records are inserted or updated.

Example:

```http
GET /api/alerts?status=NEW&severity=HIGH&sort_order=desc&page=1&page_size=20
Authorization: Bearer <access_token>
```

To fetch the next page, send the same filters and `page_size` with `page=2`.
For 45 matching alerts and `page_size=20`, the response contains `total_pages=3`.
Page 2 returns 20 alerts with both navigation flags true; page 3 returns the
remaining 5 alerts with `has_next=false`.

## Details

`GET /api/alerts/{id}` accepts an alert UUID and returns `200 OK`. The response
contains the five alert fields above plus a nested `detection` object:

| Detection fields | Contents |
| --- | --- |
| `detection_id`, `configuration_id` | Detection UUID and optional configuration UUID |
| `created_at`, `first_ingested_at` | Creation and optional first ingestion timestamp |
| `type`, `method`, `severity`, `confidence` | Classification and optional confidence |
| `src_ip`, `dst_ip`, `src_port`, `dst_port`, `protocol` | Optional network endpoints and protocol |
| `window_size_s`, `window_start`, `window_end` | Optional detection window |
| `explanation`, `features`, `trace_ids` | Optional explanation, optional feature object and array of trace IDs |

Nullable fields are returned as `null`; missing trace IDs are an empty array.
The handler eagerly loads the detection in the same query. Read operations do
not modify alert or detection records.

## Acknowledge

```http
PATCH /api/alerts/00000000-0000-0000-0000-000000000001/acknowledge
Authorization: Bearer <access_token>
```

No request body is needed. Returns `200 OK` with the five alert fields:
`status` becomes `ACKNOWLEDGED` and `acknowledged_at` is set to the database's
current transaction time. Alert and detection identifiers and creation time
are preserved. The handler commits before returning success.

An atomic `UPDATE ... RETURNING` uses `COALESCE(acknowledged_at, now())` to
preserve an existing acknowledgement time. Repeated and concurrent requests
return the same timestamp. Other alerts and the related detection are unchanged.
The existing schema stores status and time, without an acknowledging user ID.

## Errors and implementation

| Status | Cause |
| --- | --- |
| `401` | Missing, invalid or expired access token, refresh token, or deleted user; includes `WWW-Authenticate: Bearer` |
| `404` | Unknown alert UUID for details or acknowledgement; `{"detail": "Alert not found"}` |
| `422` | Invalid query parameter, time range, pagination or path UUID; `{"detail": [...]}` |
| `503` | Database operation failed; `{"detail": "Database storage unavailable"}` |

The implementation follows one operation per folder: controller, query or command,
handler and response. List query validation lives in its request model. Controllers
construct handlers directly; dependencies provide authentication and the database.
The existing schema is used without migrations. OpenAPI is available at `/docs`.

[Integration tests](../../../../services/api/tests/integration/test_alerts.py) cover
both roles, authentication failures on all routes, individual and combined filters,
IPv6 normalization, half-open time boundaries, optional bounds, stable sorting,
pagination, empty pages, complete and nullable detection details, persisted and
concurrent acknowledgement, unchanged unrelated rows, validation and OpenAPI.
[Unit tests](../../../../services/api/tests/unit/test_list_alerts_request.py) cover
optional bounds and timezone-aware range validation. Integration tests use the
existing disposable TimescaleDB setup without mocks or dependency overrides.

[Endpoint plan](../endpoints.md) · [Test setup](../../../../services/api/tests/README.md)
