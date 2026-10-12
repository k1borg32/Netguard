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
| Dashboard | nginx (placeholder, React later) | 3000 |
| Broker UI (optional) | Redpanda Console | 8081 |

## Requirements

- Docker Desktop (or Docker Engine) with Compose v2, **at least 6 GB RAM** given to Docker
- Python 3.11+ for running tests locally
- `make` (Linux/macOS; on Windows use Git Bash/WSL or run the commands from the Makefile by hand)

## Run it (NFR05 - one procedure)

```bash
cp .env.example .env      # edit passwords if you like
docker compose up -d --build
make sim                  # start traffic, Ctrl+C to stop
```

Open http://localhost:3000 - port-scan detections appear within ~15 s.
API docs: http://localhost:8000/docs. Broker UI: `docker compose --profile debug up -d`, then http://localhost:8081.

Stop: `make down`. Wipe all data: `make reset`.

## Configuration

| File | What |
|---|---|
| `.env` | Credentials, log level, simulator rate. Never committed. |
| `config/detection.yaml` | Windows (1/10/60 s), rule thresholds, statistical method parameters |
| `libs/common/.../schemas/*.json` | Message contracts |

## Tests

```bash
make setup         # venv + dev tools
make test          # unit tests (no Docker needed)
make up && make test-int   # integration tests against the running stack
make lint
```

CI (GitHub Actions) runs lint, unit tests, a secrets scan, and integration tests with the full stack on every PR.

## Demo commands

| Requirement | Command |
|---|---|
| NFR01 load (5,000 flows/s, 5 min) | `make perf` |
| NFR03 scaling | `make scale` (3 processor instances) |
| NFR04 resilience | `make kill-one` while `make sim` runs - detections keep coming |
| F15 traceability | copy a `trace_id` from a detection, `make trace ID=<id>` |

## Team conventions

See [`Docs/CONVENTIONS.md`](Docs/CONVENTIONS.md) - topics, schemas, trace IDs, branching, definition of done.
