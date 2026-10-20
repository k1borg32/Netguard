# NetGuard - Network Anomaly Detection Platform

Defensive, lab-only platform: imports PCAP/flow data or simulated traffic, processes it as a stream,
detects and classifies anomalies (rules + statistical method), stores results, and shows them in an API and dashboard.
**No real networks, no real attacks, no production data.**

> Status: week 1-2 skeleton. A thin pipeline (simulator -> broker -> processor -> persister -> DB -> API -> dashboard)
> works with a placeholder port-scan rule. Components get replaced by their owners per the schedule.

## Architecture (current)

```
simulator --+                      +--> processor (xN) --> [detections] --+
            +--> [flows.raw] ------+                                      +--> persister --> TimescaleDB --> API --> dashboard
importer  --+    key = src_ip      +--------------------------------------+
```

| Component | Tech | Port |
|---|---|---|
| Broker | Redpanda (Kafka API) | 19092 |
| DB | PostgreSQL 16 + TimescaleDB | 5432 |
| API | FastAPI | 8000 |
| Dashboard | React + nginx | 3000 |
| Broker UI (optional) | Redpanda Console | 8081 |

All ports are published on `127.0.0.1` only, so the DB and broker (no real auth in dev) are not reachable from your network.

## Requirements

- Docker Desktop (or Docker Engine) with Compose v2, **at least 6 GB RAM** given to Docker
- Python 3.12 for running tests locally (same version as CI and the containers)
- `make` is optional. On Windows: `winget install ezwinports.make` and use Git Bash, or run the commands below directly.

## Run it (NFR05 - one procedure)

```bash
cp .env.example .env      # edit passwords if you like
docker compose up -d --build
make sim                  # start traffic, Ctrl+C to stop
```

Windows PowerShell, without make:

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose --profile sim run --rm simulator
```

Create the first dashboard user once per DB volume (asks for a username and a password of 12+ characters):

```bash
docker compose exec api python -m app.infrastructure.bootstrap_admin
```

Open http://localhost:3000 and sign in - port-scan detections appear within ~15 s.
Dashboard development: [services/dashboard/README.md](services/dashboard/README.md).
API docs: http://localhost:8000/docs. Broker UI: `docker compose --profile debug up -d`, then http://localhost:8081.

Stop: `make down`. Wipe all data: `make reset` (`docker compose down -v`).

## Configuration

| File | What |
|---|---|
| `.env` | Credentials, log level, simulator rate. Never committed. |
| `config/detection.yaml` | Windows (1/10/60 s), rule thresholds, statistical method parameters |
| `libs/common/.../schemas/*.json` | Message contracts |

## Tests

What we test, how and when is described in the [test plan](Docs/TestPlan/README.md).

```bash
make setup                 # venv + dev tools
make test                  # unit + API integration tests (Docker database starts automatically)
make test-unit             # unit tests only (no Docker needed)
make test-int              # API integration tests with a disposable Docker database
make up && make test-stack # smoke tests against the full running stack
make coverage              # unit tests + coverage report
make lint                  # ruff lint + format check, same as CI
```

Without make (activate the venv first: `.venv\Scripts\Activate.ps1` on Windows, `source .venv/bin/activate` elsewhere):

```bash
python -m venv .venv
pip install -e "libs/common[kafka]" -r requirements-dev.txt
pytest                     # unit + API integration tests; Docker Desktop must be running
pytest -m "not integration" # unit tests only, without Docker
pytest -m stack            # full-stack smoke tests; stack must be running
ruff check . && ruff format --check .
```

CI (GitHub Actions) runs lint, unit tests with coverage, a secrets scan, API integration tests with their own
disposable TimescaleDB, and full-stack smoke tests on every PR. Test cases run sequentially.
The API test database starts once per session, is cleared before and after each test, and is removed at the end.
See [API test structure and seeds](services/api/tests/README.md) for adding new tests.

## Demo commands

| Requirement | Command |
|---|---|
| NFR01 load (5,000 flows/s, 5 min) | `make perf` (generates the load; measuring is part of the performance tests) |
| NFR03 scaling | `make scale` (3 processor instances) |
| NFR04 resilience | `make kill-one` while `make sim` runs - detections keep coming. The killed container stays down (`docker kill` counts as a manual stop); the others take over its partitions within ~10 s. |
| F15 traceability | copy a `trace_id` from a detection, `make trace ID=<id>` |

## Troubleshooting

- **DB container gets recreated "for no reason" (Windows).** Compose turns `./db/init` into an absolute path, and
  `d:\netguard` vs `D:\netguard` counts as a different config. VS Code terminals often use the lowercase drive letter,
  PowerShell the uppercase one. Stick to one terminal, or use `make scale` (it only touches the processor).
- **Port already in use** (5432, 8000, 3000): something else is running on that port, e.g. a local PostgreSQL.
  Stop it or change the left side of the port mapping in `docker-compose.yml`.

## Docs

- [Vision Document](Docs/VisionDoccument/README.md) - requirements F01-F17, NFR01-NFR11
- [Test Plan](Docs/TestPlan/README.md)
- [Team conventions](Docs/CONVENTIONS.md) - topics, schemas, trace IDs, branching, definition of done
