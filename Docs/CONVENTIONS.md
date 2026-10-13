# Team conventions (agree in week 1, don't change without telling everyone)

## 1. Repo layout

M1-M5 are the roles from the project spec (section 9):

| Role | Who | Area |
|---|---|---|
| M1 | Valeriia | Network Data & Flow Processing |
| M2 | Kuzma | Anomaly Detection & Algorithms |
| M3 | Jakub | Backend & Data Storage |
| M4 | Daniyar | Frontend & Visualization |
| M5 | Vlad | Infrastructure, Testing & DevOps |

| Path | Owner | What |
|---|---|---|
| `libs/common/` | M5 | Shared schemas, logging, broker helpers. **Every service uses it.** |
| `services/importer/` | M1 | PCAP / flow-file import + normalisation (week 3) |
| `services/simulator/` | M1 (load mode: M5) | Synthetic traffic + 4 scenarios |
| `services/processor/` | M2 | Windows, rules, statistical method |
| `services/persister/`, `services/api/`, `db/` | M3 | Persistence, classification, REST API |
| `services/dashboard/` | M4 | React dashboard |
| `docker-compose.yml`, `.github/`, `tests/integration/`, `tests/perf/` | M5 | Infra, CI, system/perf/resilience tests |
| `config/detection.yaml` | M2 | Rule thresholds and windows |
| `Docs/` | everyone | Vision, architecture, test plan/report |

## 2. Message formats

Schemas: `libs/common/src/netguard_common/schemas/`. They are the contract between components.

- `flow.v1.json`: topic `flows.raw`, **key = src_ip**
- `detection.v1.json`: topic `detections`, key = detection_id
- Changing a field: open a PR that touches the schema + a test, tag the whole team. Breaking change = new `schema_version`.

Why key by src_ip: flows from one source always hit the same partition, so they're always processed by the same processor instance. Without this, scaling the processor breaks per-source windows.

## 3. Trace IDs (F15, NFR08)

- The **first** component that touches data creates `trace_id` (importer or simulator).
- Every downstream message copies it (detections carry a sample in `trace_ids`).
- Every log line is emitted inside `with trace_context(trace_id):` so it appears in the JSON.
- Debug any event: `make trace ID=<trace_id>`.

## 4. Latency measurement (NFR02)

- `ingested_at` = time NetGuard accepted the flow (set once, never overwritten).
- Detection carries `first_ingested_at` and `created_at`.
- `latency = created_at - first_ingested_at`. View `detection_latency` in the DB, p95 computed by the perf test.

## 5. Delivery and duplicates

At-least-once. Consumers commit offsets **after** the work is done. So every write must be idempotent:
deterministic IDs (`flow_id_for`, `detection_id`) + `ON CONFLICT DO NOTHING`.

## 6. Logging

`setup_logging("<service>")` at startup, `get_logger(__name__)` everywhere. No `print`.
Levels: INFO for lifecycle and detections, WARNING for recoverable problems, ERROR for dropped data.
Never log secrets or full payloads at INFO.

## 7. Git

- `main` is protected: PR + 1 review + green CI.
- Branches: `feat/<area>-<short>`, `fix/...`, `test/...`, `docs/...`.
- Small PRs. Integrate continuously; don't sit on a branch for two weeks.

## 8. Secrets

Only in `.env` (git-ignored). `.env.example` holds placeholders. CI runs gitleaks on every push.

## 9. Definition of done (per feature)

Code + unit test + runs in `docker compose up` + logs with trace_id + doc line in README if it adds a command +
CI green. If a test covers a requirement from the [test plan](TestPlan/README.md), put the test case ID
(e.g. `IT-02`) in its docstring, so the traceability table stays true.
