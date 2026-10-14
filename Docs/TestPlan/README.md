# NetGuard - Test Plan v0.2

Preliminary version, week 1 (2026-10-14), updated for Vision v1.1. Owner: Vlad (M5, Infrastructure, Testing & DevOps).
Next updates: week 2 (after the architecture document) and week 5 (after the first version of the detection engine).

## 1. Introduction

This plan describes what we test in NetGuard, how, where, when and who does it, and when a part counts as done.
It follows section 14 of the project specification and covers the requirements from the
[Vision Document](../VisionDoccument/README.md) (v1.1: F01-F17, NFR01-NFR11).

Testing is part of development, not a phase at the end. Every feature comes with its tests (definition of done in
[CONVENTIONS](../CONVENTIONS.md)), CI runs them on every pull request, and results go into the test report during the
whole project, not only in week 9.

References:

- Project specification "Network Anomaly Detection Platform - NetGuard" v1.0, mainly sections 4 (functions),
  5 (scenarios), 14 (tests) and 15 (non-functional requirements)
- Vision Document v1.0
- Team conventions: message contracts, trace IDs, latency, delivery semantics
- Message schemas: `libs/common/src/netguard_common/schemas/`

## 2. Scope

### 2.1 Test items

| Component | Code | Owner | State in week 1 |
|---|---|---|---|
| Traffic simulator | `services/simulator` | M1 (load mode M5) | normal traffic + port scan |
| PCAP importer | `services/importer` | M1 | planned, week 3 |
| Broker + message contracts | Redpanda, `libs/common` | M5 | working |
| Flow processor / detection engine | `services/processor` | M2 | placeholder port scan rule |
| Persister + database | `services/persister`, `db/` | M3 | working, schema v1 |
| REST API | `services/api` | M3 | health + list of detections |
| Dashboard | `services/dashboard` | M4 | placeholder page |
| Deployment and CI | `docker-compose.yml`, `.github/` | M5 | working |

### 2.2 In scope

All functional requirements F01-F17 and non-functional requirements NFR01-NFR11 from Vision v1.1. Section 11 maps
every requirement to test cases.

### 2.3 Out of scope

- live capture from real networks and any traffic leaving the lab machine (spec 16, NFR09)
- attack tools: anomalous traffic only comes from the simulator and prepared files
- high availability of the broker and the database (one node each). We test failure of processing instances and
  recovery after a broker/DB restart, not clustering
- full SIEM/IDS functionality and real-world detection rates
- browsers other than current Chrome and Firefox
- usability tests with real operators (only an informal review inside the team in week 7)

## 3. Test approach

### 3.1 Overview

| Type | What it shows | Tools | Where / when | Owner |
|---|---|---|---|---|
| Unit | single functions: parsers, features, windows, rules, statistics, schemas | pytest, pytest-cov | locally + CI on every PR | author of the code |
| Integration | components working together through the real broker and DB | pytest + Docker Compose | CI on every PR | M5 + component owner |
| API | endpoints, contract, errors, authorization | pytest, Schemathesis (week 9) | CI on every PR | M3 + M5 |
| System (end to end) | input -> detection -> dashboard | pytest, Playwright | CI smoke + before demos | M5 + M4 |
| Detection quality | precision, recall, F1, false positives/negatives | evaluation script, labelled datasets | from week 5, final in week 9 | M2 + M5 |
| Performance | throughput, latency, resource usage | simulator load mode, measurement script, docker stats, k6 | baseline week 4, campaign week 8 | M5 |
| Resilience | failure and restart of components, recovery | pytest + docker CLI | CI smoke + campaign week 8-9 | M5 |
| Security | input validation, auth, rate limiting, secrets, dependencies | pytest, gitleaks, pip-audit, Trivy, OWASP ZAP | CI + campaign week 9 | M5 + M3 |

Plain `pytest` runs only unit tests (no Docker needed). `pytest -m integration` runs the tests that need the running
stack. New groups (for example resilience) get their own pytest marker when their first test is written.

### 3.2 Unit tests

- live in `tests/unit`, no network and no Docker, the whole suite runs in under 30 s
- deterministic: fixed timestamps and seeds, no assertions on the wall clock
- every rule is tested on both sides of its threshold (fires above, stays silent below) and on a window boundary
- coverage is reported in CI. Target: at least 80 % of lines in `libs/common` and in the detection logic by week 6.
  Week 1 baseline: 69 % overall. No coverage target for UI code.

### 3.3 Integration tests

- run against the same compose stack as the demo (one configuration, NFR05)
- every test uses its own fresh source IPs and only checks detections it caused itself. The stack is shared, so the
  order of tests must not matter
- waiting is done by polling with a deadline, never with a fixed sleep
- main chain from spec 14: importer/simulator -> broker -> processor -> detector -> database -> API
- contracts: messages are checked against the JSON schemas in `libs/common`. A schema change is a PR with a test
  (CONVENTIONS, section 2)

### 3.4 API tests

For every endpoint: a valid request, invalid parameters (422), missing object (404), no token (401), non-admin on an
administrative operation (403), rate limit (429), and the response matches the OpenAPI schema. The filters from F13
(time, type, severity, source) are checked against data we inserted ourselves. From week 9 Schemathesis generates
requests from the OpenAPI schema and checks that the API never answers with 500.

### 3.5 System tests

Complete scenarios: start the stack with the documented procedure, feed a known input (simulator scenario with a fixed
seed or a prepared PCAP) and check the alert and its evidence in the API and on the dashboard. The dashboard is
checked with Playwright (headless Chromium) from week 7. Before the mid-term and the final presentation we go through
the demo checklist by hand on a clean clone of the repository.

### 3.6 Detection quality tests

NFR11 asks for precision, recall and F1 per class on a common labelled test set.

**Ground truth.** Every simulated flow has a `label`. On top of that the simulator writes a manifest of attack
episodes: class, attacker IP(s), target IP(s), start and end time. For PCAP datasets we write the manifest by hand from
the dataset description and a second person checks it. Detectors never see the labels: DQ-07 runs the detection with
labels removed and expects exactly the same result.

**Matching detections to episodes.**

- a detection matches an episode when the class is the same, the detection's source (destination for DDoS with many
  sources) belongs to the episode, and the detection window overlaps the episode time (plus/minus one window)
- precision of class c = detections of class c that match an episode of class c / all detections of class c
- recall of class c = episodes of class c matched by at least one detection of class c / all episodes of class c
- F1 = 2PR / (P + R), macro average over the five attack classes
- several detections of one episode (for example one per window) count as one match for recall. We also report
  alerts per episode, because too many alerts are a problem for the operator
- a detection with the wrong class counts as a false positive for the predicted class and a false negative for the
  real class (unless another detection got it right). `unknown` detections that hit an episode are reported
  separately as "detected but not classified"
- false alarms: alerts per hour on the normal-only dataset

We report a table per class, a confusion matrix (real class x predicted class + "missed"), and for every false
positive / false negative of the final run the reason (threshold, window boundary, traffic mix) and what we changed.

**Threshold sweep.** For the main threshold of every rule we plot precision and recall over a range of values (for
example 20-200 unique ports) to justify the default in `config/detection.yaml`.

**Targets** (NFR11, reviewed in week 5 after the first measurement):

- port scan, DoS, brute force (rule based): precision >= 0.90 and recall >= 0.90 on the synthetic set
- macro F1 >= 0.80 over all five attack classes on the synthetic set
- 30 min of normal traffic: no HIGH/CRITICAL alert and at most 2 alerts per 10 minutes
- PCAP set: no fixed target, results reported together with the error analysis

### 3.7 Performance tests

**Metrics:**

- throughput: flows/s accepted (sent to `flows.raw`), processed and stored
- detection latency (NFR02): from the ingestion of the last flow that contributed to a detection until the detection
  is created, so `created_at - last_ingested_at`. The detection contract doesn't have `last_ingested_at` yet
  (risk R2)
- p50 / p95 / p99 / max of the latency
- consumer lag of the processor and persister groups, sampled every 5 s. Lag that keeps growing means the system
  can't keep up
- CPU and memory per container (`docker stats`, every 5 s)
- lost or rejected messages and producer delivery errors (logged as "message not delivered")

**Load levels (NFR01):** 100, 1,000, 5,000 and 10,000 flows/s, then further steps up to 50,000 flows/s or until the
system saturates; we report how far one machine gets. Every level gets 1 min of warm-up (not measured)
and 5 min of measurement. About 2 % attack traffic is mixed in, so detections (and therefore latency values) exist
during the run. The generator has to reach the requested rate, otherwise the run is invalid. For high rates we run
several simulator instances.

**Pass criteria:**

- NFR01: 5,000 flows/s for 5 min, the consumer lag does not grow, no messages lost
- NFR02: p95 latency <= 3 s at 5,000 flows/s, without failures
- NFR03: saturation point measured with 1 and with 3 processor instances

**Conditions recorded with every result** (spec 14): CPU, cores, RAM, OS, resources given to Docker, git commit,
configuration (`detection.yaml`, number of instances and partitions), simulator settings and date. The official
campaign runs on one fixed machine (chosen in week 8). We do not compare numbers from different machines.

**API load:** k6 with 50 virtual users that poll the alert list every 2 s, like the dashboard does. We report the p95
response time (informational, there is no NFR for it).

### 3.8 Resilience tests

Spec 15 asks for at least one controlled failure scenario. We plan seven (RT-01 to RT-07). For each one we write down
what we break, how, what should happen, and what we measure: time to recover, missed detections, duplicate alerts,
lost flows.

How we break things:

- `docker kill <container>`: the instance dies and stays down. Docker treats it as a manual stop, so the restart
  policy does not apply (checked in week 1)
- killing the process inside the container: a crash, the restart policy brings the container back
- `docker compose stop` / `start` of the broker or the DB: an outage of the infrastructure

Known limitation: the processor commits offsets before its windows close, so an instance that dies loses its open
windows (at most one window per source). RT-01 and RT-02 count how many detections this costs.

### 3.9 Security tests

From NFR06 and spec 14: input validation, authentication and authorization, rate limiting and basic API/application
vulnerabilities, plus secrets and dependencies. CI already runs gitleaks on every push. pip-audit, a Trivy image scan
and an OWASP ZAP baseline scan are added in week 9.

## 4. Test environment

| Environment | Used for | Setup |
|---|---|---|
| Developer machine | unit tests, quick integration runs | Docker Desktop/Engine with Compose v2, >= 6 GB RAM for Docker, Python 3.12, `docker compose up -d --build` |
| CI | every PR and every push to `main` | GitHub Actions `ubuntu-latest`: lint + unit tests with coverage, gitleaks, integration tests on the full stack |
| Performance machine | performance and resilience campaign | one fixed machine, specs recorded, nothing else running |

- the same compose file and configuration everywhere. Tests use the committed defaults unless a test case says
  otherwise
- everything runs in local Docker networks, ports are bound to 127.0.0.1, no traffic leaves the machine (NFR09)
- image versions are pinned in compose (Redpanda, TimescaleDB, nginx); Python 3.12 in CI and in the containers

## 5. Test data

| ID | Content | Source | Used by | Ready |
|---|---|---|---|---|
| FX | small flow and detection fixtures | written in the tests | unit tests | week 1 (exists) |
| SIM-NORMAL | normal traffic only, 30 min at 1,000 flows/s, fixed seed | simulator | false alarms, DQ | week 4 |
| SIM-SCEN | each of the 5 scenarios several times, including weak variants near the thresholds, with normal background and a manifest | simulator | DQ, integration | week 4-5 |
| SIM-LOAD | load profiles from 100 flows/s to saturation, about 2 % attacks | simulator load mode | performance | week 4 (baseline), week 8 |
| PCAP-SMALL | small hand-made PCAPs, also broken ones | written offline with Scapy (packets go straight into a file, nothing is sent) | importer unit tests, security | week 3 |
| PCAP-SET | labelled PCAPs from the course, or a subset of a public labelled dataset (e.g. CIC-IDS2017) if none is provided | offline files | DQ on data we didn't generate | week 3 |
| BAD-INPUT | schema-invalid flows, broken and oversized files, injection strings | written in the tests | security, resilience | week 3 / 9 |

Big files stay outside git (`data/pcap` is git-ignored) with a checksum list in the repository. Simulator datasets
are not stored; they are reproduced from configuration + seed.

## 6. Entry and exit criteria

| Level | Entry | Exit |
|---|---|---|
| Unit | code passes lint | all tests pass; coverage target for core modules met (from week 6) |
| Integration / API / system | stack starts with the documented command, all healthchecks green, unit tests pass | all tests pass in CI on `main` |
| Detection quality | detection engine complete for the measured classes, datasets and manifests ready | metrics for all classes, every false positive/negative of the final run explained |
| Performance / resilience campaign (weeks 8-9) | feature freeze for the measured components, system tests pass, performance machine prepared | all planned runs done and recorded with their conditions |
| Final release (week 10) | all of the above | all critical and high test cases pass; NFR01 and NFR02 met, or the gap explained with measurements; no open critical/high defects; test report complete |

**Suspension and resumption.** If the stack does not start from a clean clone or CI on `main` is red, system and
performance testing stops until that is fixed and CI is green again. A performance run is invalid and repeated if the
generator did not reach the requested rate or something else was running on the machine.

## 7. Defect management

- GitHub Issues with the label `bug` and a severity: critical (pipeline stops, data loss, security hole),
  high (wrong detection result, requirement not met), medium, low
- an issue contains steps to reproduce, expected and actual result, commit, trace_id or logs, and the test case ID
- a fixed defect gets a regression test before the issue is closed
- triage at the weekly team meeting

## 8. Roles and responsibilities

| Who | Testing responsibilities |
|---|---|
| Everyone | unit tests for their own code, runs the tests before opening a PR, reviews tests in PRs, takes part in the week 9 campaign (spec 9) |
| M1 - Valeriia (Network Data & Flow Processing) | importer and simulator tests, PCAP test files, ground-truth manifests |
| M2 - Kuzma (Anomaly Detection & Algorithms) | unit tests for windows, rules and statistics; detection quality evaluation together with M5; threshold sweeps |
| M3 - Jakub (Backend & Data Storage) | API and persistence tests; API security tests (auth, rate limiting) together with M5 |
| M4 - Daniyar (Frontend & Visualization) | dashboard component tests; Playwright end-to-end tests together with M5 |
| M5 - Vlad (Infrastructure, Testing & DevOps) | test plan and report, CI, test environment, automation of integration/system/performance/resilience/security tests, coordination |

## 9. Schedule

| Week | Test work |
|---|---|
| 1 | test plan v0.1, v0.2 for Vision v1.1; CI with lint, formatting, unit tests + coverage, gitleaks, integration tests; check of the dev environment (section 10) |
| 2 | plan updated with the architecture; detection contract updated to Vision v1.1: `last_ingested_at` and the six classes (R2, R7); ground-truth manifest format with M1 and M2 |
| 3 | importer: unit tests, broken PCAPs (SEC-02), PCAP -> flow integration tests (IT-03, IT-05) |
| 4 | simulator scenario tests; SIM-* datasets; first performance baseline at 100 / 1,000 / 5,000 flows/s (PT-01, PT-02), shown at the mid-term presentation |
| 5 | detection unit tests; evaluation script; first precision/recall/F1 (DQ-01 to DQ-08); targets revisited |
| 6 | API tests including filters, auth and rate limiting (API-01 to API-09, SEC-03 to SEC-07); persistence tests |
| 7 | dashboard end-to-end smoke tests with Playwright (ST-02 to ST-05, SEC-08) |
| 8 | performance campaign (PT-01 to PT-06); resilience scenarios (RT-01 to RT-07) |
| 9 | full regression, final detection quality on the common test set, security scans, test report |
| 10 | re-test of fixes, demo rehearsal on a clean clone (ST-06) |

## 10. Risks

In week 1 we started the skeleton with the documented command and ran the existing tests: 18 unit tests and 2
integration tests passed (2026-10-13, Docker Desktop on Windows 11, 8 CPUs / 8 GB for Docker). While checking the
environment we also scaled the processor, killed an instance and sent invalid data. What we found is part of the
table below. After the week-1 fixes the stack was rebuilt from scratch and the integration tests passed again
(2026-10-14).

| ID | Risk / finding | Impact | What we do |
|---|---|---|---|
| R1 | The Python pipeline may not reach 5,000 flows/s. Full JSON-schema validation alone costs about 0.12 ms per flow (measured), that is about 60 % of one CPU core at 5,000 flows/s. | NFR01 | performance baseline already in week 4; validate everything at the edge (importer, simulator) instead of again in every consumer; batch DB writes; scale the processor |
| R2 | Vision v1.1 measures NFR02 from the last flow that contributed to a detection, but the detection contract only has `first_ingested_at`. Measured from the first flow, the latency contains the whole window (>= 10 s for a 10 s window), so 3 s can never pass. | NFR02 can't be measured correctly yet | week 2: add `last_ingested_at` to the detection contract and to the `detection_latency` view; M2 to consider firing a rule as soon as its threshold is crossed |
| R3 | One malformed message on `flows.raw` makes the consumers crash in a loop (processor: missing field -> KeyError; persister: invalid IP -> DB error). The offset is never committed, so they read the same message again after every restart. Reproduced in week 1. | pipeline stops (critical) | importer and simulator validate everything they send; consumers isolate a failing record (skip it and put it on `flows.deadletter`, which exists but is unused) instead of crashing; RT-06, SEC-01 |
| R4 | Slow failover: after killing one of two processors its partitions waited 44 s (librdkafka default session timeout is 45 s). A crashed persister also blocked its own restart for about 45 s. The CI step "kill one processor" waits only 40 s, so it would fail about half of the time. | NFR04, flaky CI | session timeout lowered to 10 s in `libs/common` (week 1), to be re-measured with RT-01; the persister should close its consumer when it exits (M3) |
| R5 | The persister crashes when the DB connection drops and does not reconnect (seen when the DB container was recreated). | data not stored until the restart | the restart policy covers it for now; reconnect with backoff in week 6 (M3); RT-04 |
| R6 | Windows: compose recreated the DB container when started from `d:\netguard` instead of `D:\netguard` (bind-mount paths are part of the configuration). | unexpected restarts during a demo | documented in the README; `make scale` only touches the processor; later the init files can be built into the image |
| R7 | The message contract still has the old four detection types, Vision v1.1 has the six classes from the spec (Abnormal Traffic and Suspicious Connection Pattern split, Unknown Anomaly added). | per-class quality for the six classes not possible yet | contract update in week 2, together with R2 |
| R8 | Performance numbers depend on the laptop. | results not comparable | one fixed machine, conditions recorded |
| R9 | Flaky integration tests (timing, shared stack). | people start ignoring CI | polling with deadlines, unique data per test, logs uploaded when CI fails |
| R10 | Ground truth for PCAP datasets may be wrong. | wrong precision/recall | start with synthetic data; manifests checked by two people |
| R11 | Windows/Linux differences (line endings, make, paths). | "works on my machine" | `.gitattributes` (LF), everything runs in Docker, CI on Linux, Windows steps in the README |

Also fixed in week 1: the DB, broker, API and dashboard were published on all network interfaces with a default
password (now 127.0.0.1 only, SEC-11), and there was no `.dockerignore`, so the whole repository including `.venv` and
`.env` was sent to every image build.

## 11. Traceability

| Requirement | Test cases |
|---|---|
| F01 Data ingestion | UT-01, UT-11, IT-03, IT-05, SEC-02, DQ-05 |
| F02 Flow extraction | UT-01, UT-11, IT-03 |
| F03 Feature extraction | UT-12 |
| F04 Stream processing | IT-02, IT-04 |
| F05 Time windows | UT-06, UT-13, DQ-06 |
| F06 Rule-based detection | UT-07, UT-08, UT-14, IT-04, DQ-01, DQ-02, DQ-04, DQ-06 |
| F07 Second detection method | UT-15, IT-04, DQ-01, DQ-02, DQ-03 |
| F08 Classification | UT-02, UT-16, IT-07, DQ-03, DQ-07 |
| F09 Explainability | UT-07, IT-07, DQ-08, ST-02 |
| F10 Database | UT-03, IT-02, IT-05, IT-07, RT-03, RT-07 |
| F11 REST API | IT-01, IT-02, API-01 to API-06, PT-05 |
| F12 Dashboard | ST-02, ST-03, ST-05 |
| F13 Filtering | API-03, ST-04 |
| F14 Simulator | UT-05, UT-18, IT-04, API-06 |
| F15 Traceability | UT-04, IT-06 |
| F16 Detection configuration | UT-17, API-07, DQ-04 |
| F17 Alert management | IT-08, API-08 |
| NFR01 Performance | PT-01, PT-02, PT-06 |
| NFR02 Latency | PT-03 |
| NFR03 Scalability | PT-04, RT-01 |
| NFR04 Resilience | UT-03, UT-09, UT-10, RT-01 to RT-07 |
| NFR05 Reproducibility | ST-01, ST-06, RT-07 |
| NFR06 Security | UT-01, API-02, API-09, SEC-01 to SEC-12 |
| NFR07 Testability | unit and integration suites in CI, coverage report |
| NFR08 Observability | UT-04, IT-06 |
| NFR09 Data | ST-01 (everything runs locally), test data sources in section 5 |
| NFR10 Documentation | ST-06 |
| NFR11 Detection quality | DQ-01, DQ-02, DQ-03, DQ-05 |

## 12. Test cases

Status: **pass** = automated and passing in week 1, **fails** = reproduced problem (see risks), otherwise the week in
which the test is planned. Automated tests carry their ID in the docstring.

### Unit tests (UT)

| ID | Test | Req. | Expected result | Where | Status |
|---|---|---|---|---|---|
| UT-01 | Flow schema: valid flow accepted; wrong types, bad IP, port out of range, unknown or missing field rejected | F01, F02, NFR06 | invalid flows raise `SchemaError` naming the field | `tests/unit/test_messages.py` | pass |
| UT-02 | Detection schema rejects unknown severity and confidence outside 0-1 | F08 | `SchemaError` | `tests/unit/test_messages.py` | pass |
| UT-03 | Deterministic flow and detection IDs | F10, NFR04 | same input -> same ID, so re-imports and redelivery don't duplicate rows | `tests/unit/test_messages.py` | pass |
| UT-04 | Log lines are JSON with service name and trace_id | F15, NFR08 | trace_id set inside `trace_context`, null outside | `tests/unit/test_logging.py` | pass |
| UT-05 | Simulator output matches the flow schema | F14 | 500 generated flows are valid | `tests/unit/test_pipeline_logic.py` | pass |
| UT-06 | A window closes only after its size + grace period | F05 | not closed at 10.5 s, closed at 11 s | `tests/unit/test_pipeline_logic.py` | pass |
| UT-07 | Port scan above the threshold | F06, F09 | valid detection with unique ports, threshold and window as evidence | `tests/unit/test_pipeline_logic.py` | pass |
| UT-08 | Normal traffic | F06 | no port scan detection | `tests/unit/test_pipeline_logic.py` | pass |
| UT-09 | Same flows processed twice | NFR04 | same `detection_id` | `tests/unit/test_pipeline_logic.py` | pass |
| UT-10 | Consumer helper gets an undecodable message | NFR04 | message skipped and logged, the rest is processed | `tests/unit/test_broker.py` | pass |
| UT-11 | PCAP parser on a known PCAP | F01, F02 | expected flows (5-tuple, packets, bytes, duration) | | week 3 |
| UT-12 | Feature extraction per window | F03 | correct connection rate and unique ports/addresses | | week 3-5 |
| UT-13 | 1 s, 10 s and 60 s windows, flows on window boundaries | F05 | each flow counted in the right window | | week 5 |
| UT-14 | DoS, brute force and suspicious connection pattern rules | F06 | fire above the threshold, silent below | | week 5 |
| UT-15 | Statistical method | F07 | baseline built, abnormal traffic detected as a deviation from it, other anomalies reported as `unknown`, no result before the minimum number of baseline windows | | week 5 |
| UT-16 | Severity and confidence | F08 | values follow the ratios in `detection.yaml` | | week 5 |
| UT-17 | Invalid or missing values in `detection.yaml` | F16 | service refuses to start with a clear error | | week 5 |
| UT-18 | Simulator parameters | F14 | number of hosts, rate and anomaly ratio respected; same seed -> same output | | week 4 |

### Integration tests (IT)

| ID | Test | Req. | Expected result | Where | Status |
|---|---|---|---|---|---|
| IT-01 | API health | F11 | `status: ok`, DB reachable | `tests/integration/test_stack.py` | pass |
| IT-02 | Port scan flows sent to the broker | F04, F06, F10, F11 | detection visible in the API within 40 s | `tests/integration/test_stack.py` | pass |
| IT-03 | PCAP import | F01, F02, F10 | flows on the broker and stored with `source = pcap` | | week 3 |
| IT-04 | Every simulator scenario | F06, F14 | the expected detection type end to end | | week 5 |
| IT-05 | Same PCAP imported twice | F10, NFR04 | no duplicate flows | | week 3 |
| IT-06 | Follow one trace_id | F15, NFR08 | found in the logs of every service and in the detection | | week 3 |
| IT-07 | Stored detection | F08, F09 | type, severity, confidence, time, source, destination, ID, features and window present | | week 6 |
| IT-08 | Alert created from a detection | F17 | alert with status `new` in the alert list, linked to its detection | | week 6 |

### API tests (API)

| ID | Test | Req. | Expected result | Status |
|---|---|---|---|---|
| API-01 | Detection list | F11 | contains every field the dashboard uses | week 6 |
| API-02 | Invalid query parameters (`limit=0`, `-1`, `501`, `abc`) | NFR06 | 422, never 500 | week 6 |
| API-03 | Filters by time, type, severity and source | F13 | only matching rows | week 6 |
| API-04 | Flow list and flow details | F11, UC-08 | correct data, 404 for unknown ID | week 6 |
| API-05 | Statistics and metrics endpoints | F11 | numbers match the database | week 6 |
| API-06 | Simulator control: configure, start, stop | F11, F14, UC-10 to UC-13 | simulator follows the commands | week 6 |
| API-07 | Change a threshold (admin) | F16 | new value used by the detection engine | week 6 |
| API-08 | Acknowledge an alert | F17 | status changes and is stored | week 6 |
| API-09 | Schemathesis on the OpenAPI schema | NFR06 | no 500 responses | week 9 |

### System tests (ST)

| ID | Test | Req. | Expected result | Status |
|---|---|---|---|---|
| ST-01 | Deployment from a clean clone with the documented command | NFR05, NFR09 | all services healthy within 5 min, integration tests pass | automated in CI (first run after push) |
| ST-02 | Simulator scenario -> dashboard | F09, F12 | alert shown with its evidence | week 7 |
| ST-03 | PCAP import -> dashboard | F01, F12, UC-01 | alerts from the file shown | week 7 |
| ST-04 | History and filters on the dashboard | F13, UC-04, UC-05 | correct rows for each filter | week 7 |
| ST-05 | Live statistics and trend charts | F12, UC-06 | values update while traffic runs | week 7 |
| ST-06 | README procedure done by someone who didn't write it, on a clean machine | NFR05, NFR10 | system runs and demo works without extra help | weeks 4 and 10 (manual) |

### Detection quality (DQ)

| ID | Test | Req. | Expected result | Status |
|---|---|---|---|---|
| DQ-01 | Precision, recall, F1 per class on SIM-SCEN | F06, F07, F08, NFR11 | NFR11 targets (section 3.6) | weeks 5 and 9 |
| DQ-02 | False alarms on SIM-NORMAL | F06, F07, NFR11 | no HIGH/CRITICAL, at most 2 alerts per 10 min | weeks 5 and 9 |
| DQ-03 | Confusion matrix including `unknown` | F08, NFR11 | reported, errors analysed | weeks 5 and 9 |
| DQ-04 | Threshold sweep for every rule | F06, F16 | default thresholds justified by the curves | week 5 |
| DQ-05 | Metrics on PCAP-SET | F01, F06, NFR11 | reported with error analysis | week 9 |
| DQ-06 | Hard cases: scan split across two windows, slow scan just below the threshold, attack hidden in heavy normal traffic | F05, F06 | behaviour documented, misses explained | week 5 |
| DQ-07 | Detection with the labels removed | F08 | exactly the same detections | week 5 |
| DQ-08 | Content of every detection | F09 | key features, threshold or deviation, window, source/destination, severity and confidence present | week 5 |

### Performance (PT)

| ID | Test | Req. | Expected result | Status |
|---|---|---|---|---|
| PT-01 | Load ladder 100 / 1,000 / 5,000 / 10,000 flows/s and up, 1 processor | NFR01 | throughput, lag and resources per level, saturation point found | week 4 (baseline), week 8 |
| PT-02 | 5,000 flows/s for 5 min | NFR01 | lag does not grow, nothing lost | weeks 4 and 8 |
| PT-03 | Latency at 5,000 flows/s | NFR02 | p95 <= 3 s (p50, p99, max reported) | week 8 |
| PT-04 | Saturation point with 1 vs 3 processor instances | NFR03 | higher with 3 instances | week 8 |
| PT-05 | API under dashboard-like load (k6, 50 users) | F11 | p95 response time reported | week 8 |
| PT-06 | CPU and memory per container per load level | NFR01 | reported, no container hits its memory limit | week 8 |

### Resilience (RT)

| ID | Test | Req. | Expected result | Status |
|---|---|---|---|---|
| RT-01 | Kill 1 of 2 processor instances, then send a port scan to every partition | NFR03, NFR04 | the other instance takes over all partitions; detections for every partition within 40 s | week 8 (manual check in week 1: 44 s before the fix, R4) |
| RT-02 | Processor process crashes inside its container | NFR04 | Docker restarts it and it rejoins the consumer group | week 8 |
| RT-03 | Persister restart under load | F10, NFR04 | no flow lost, no duplicate detections | week 8 |
| RT-04 | DB down for 30 s | NFR04 | API reports `degraded`; persister recovers; data complete afterwards | week 8 |
| RT-05 | Broker down for 30 s | NFR04 | producers and consumers reconnect; nothing lost within the producer timeout | week 8 |
| RT-06 | Malformed message on `flows.raw` | NFR04, NFR06 | consumers skip it (dead-letter topic) and keep working | fails (R3), re-test week 5 |
| RT-07 | Full restart without wiping volumes | F10, NFR05 | data kept, processing continues | week 8 |

### Security (SEC)

| ID | Test | Req. | Expected result | Status |
|---|---|---|---|---|
| SEC-01 | Schema-invalid flows sent into the pipeline | NFR06 | rejected at the edge, never crash a consumer | fails (R3), re-test week 3 |
| SEC-02 | Broken, oversized and non-PCAP files imported | F01, NFR06 | rejected with an error report, importer keeps running | week 3 |
| SEC-03 | Request without a token | NFR06 | 401 | week 6 |
| SEC-04 | Non-admin token on administrative operations (thresholds, simulator control) | NFR06 | 403 | week 6 |
| SEC-05 | Tampered or expired JWT | NFR06 | 401 | week 6 |
| SEC-06 | Injection strings in query parameters | NFR06 | 422 or empty result, no 500, no SQL error in the response | week 6 |
| SEC-07 | Too many requests from one client | NFR06 | 429 after the limit | week 6 |
| SEC-08 | HTML inside detection fields | NFR06 | shown as text on the dashboard, no script runs | week 7 |
| SEC-09 | Secret scanning | NFR06 | gitleaks on every push finds nothing; `.env` never committed | automated in CI |
| SEC-10 | Dependency audit (pip-audit, npm audit) | NFR06 | no known high/critical vulnerabilities, or documented | week 9 |
| SEC-11 | Exposed ports and container users | NFR06 | only 127.0.0.1 ports; containers run as non-root | checked in week 1, automated in week 9 |
| SEC-12 | OWASP ZAP baseline scan of API and dashboard | NFR06 | no high-risk findings | week 9 |

## 13. Reporting

Results go into the test report (`Docs/TestReport`, started with the first performance baseline in week 4). For every
executed test case it contains, as required by spec 14: test case / scenario, expected result, actual result, status
(pass / fail / blocked) and a comment. Performance and resilience runs also include the metrics and the measurement
conditions (section 3.7). CI keeps the JUnit XML and coverage report of every run as artifacts.

Example row:

| ID | Scenario | Expected | Actual | Status | Comment |
|---|---|---|---|---|---|
| RT-01 | kill 1 of 2 processors, port scan on every partition | all detected within 40 s | ... | ... | commit, machine, config |
