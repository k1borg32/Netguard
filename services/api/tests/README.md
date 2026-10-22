# API tests

Tests are split into `unit/` and `integration/`. We do not use mocks, repository
stubs, handler replacements or `app.dependency_overrides`.

## Unit

Test the models in `app/domain` in memory: domain rules, state transitions and
relationships. No HTTP, database or Docker is involved. The current models have
no business methods, so the examples verify configuration-detection-alert
relationships. Constraints enforced by SQL require integration tests.

HTTP contract validation can be checked without starting a server.
`unit/test_dashboard_summary_request.py` covers the `start_time < end_time` rule,
comparisons across timezones, the smallest positive range and an invalid start.
We do not mock SQLAlchemy sessions to test handler queries.

`unit/test_dashboard_timeseries_request.py` contains 5 essential cases:
the default start relative to the end and UTC normalization, both exact query
limits, the limit including partial buckets, and rejection of naive timestamps.

`unit/test_list_flows_request.py` covers optional flow filters, port and pagination
bounds, valid IP addresses and timezone-aware range comparisons.

## Integration

Test the full path through `client`: HTTP -> controller -> handler -> real
SQLAlchemy, Argon2 and JWT -> local TimescaleDB -> HTTP response.
Dashboard tests also cover range boundaries, timezones, invalid parameters,
access without a valid token, adjacent ranges and passing filters in the URL.
[Dashboard documentation](../../../Docs/BackendAndDataStorage/dashboard/README.md).

`integration/test_dashboard_timeseries.py` contains 13 essential cases:
aggregation of both datasets for four intervals, empty and partial buckets,
ordering, `[from, to)` boundaries, the default 24-hour range, invalid parameters,
excessive ranges and missing authentication.
[Time-series contract](../../../Docs/BackendAndDataStorage/dashboard/README.md#time-series).

- A separate Docker Compose project starts once per session on a random local port.
- The schema comes from the production `db/init/*.sql` scripts.
- Tests do not use the application's `DATABASE_URL`, existing database or volume.
- Before and after **every** integration test, all application tables are cleared
  with `TRUNCATE ... RESTART IDENTITY CASCADE`, including after failed tests.
- Each test creates a client with the application's startup and shutdown lifecycle.
- The container and test data are removed after the session.
- Tests run sequentially. Do not run them with pytest-xdist.
- Unavailable Docker or an invalid schema causes a failure, rather than a skipped test.

Fixtures in `integration/conftest.py`:

| Fixture | Scope | Purpose |
| --- | --- | --- |
| `database_url` | Session | Temporary local container and its connection URL |
| `api_environment` | Session | Configuration of real API dependencies |
| `db` | Test, automatic | Cleanup and a real psycopg connection for SQL assertions |
| `client` | Test | `TestClient` for the real application |
| `create_user` | Test | Seed a PostgreSQL account with an Argon2 password hash |

Create the first administrator with `create_user(role=UserRole.ADMIN)`.
Test registration of subsequent users through the HTTP endpoint.
Isolation does not rely on rollback: HTTP requests commit through separate connections.
New files receive the `unit` or `integration` marker automatically based on their directory.
Each test prepares its own data and does not depend on execution order.

`integration/test_flows.py` covers flow listing and details: time, IPv4/IPv6,
port and protocol filters, combined filters, stable sorting and pagination, empty
pages, the UUID + timestamp composite key, nullable fields, validation,
authentication for both roles and OpenAPI documentation.

## Running tests

From `services/api`, with the Python environment activated:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests -q
```

Integration tests require Docker Desktop running Linux containers.
There is no need to start the full application stack or configure `.env`.
The shared pytest configuration is in the repository's root `pyproject.toml`.
From the repository root, select `services/api/tests` or use `make test-int`.

Run only time-series tests, without collecting tests for other features:

```powershell
python -m pytest tests/unit/test_dashboard_timeseries_request.py -q
python -m pytest tests/integration/test_dashboard_timeseries.py -q
python -m ruff check app tests
python -m ruff format --check app tests
```
