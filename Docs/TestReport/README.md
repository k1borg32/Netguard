# NetGuard - Test Report

Started in week 4 (2026-11-03) with the first performance baseline, updated after every test campaign. Owner: Vlad
(M5). What we test and why is in the [test plan](../TestPlan/README.md); this report has the results. The status of
every test case is also in the test plan, section 12.

## 1. Automated tests on `main`

CI runs on every pull request and every push to `main`. State on 2026-11-03 (commit `9ec732b`, after #50, #55 and #63, all green):

| Suite | Where | Tests | Result |
|---|---|---|---|
| Unit | `tests/unit`, `services/api/tests/unit` | 269 | pass, 66 % line coverage (unit tests only, most of the API code is covered by its integration tests) |
| API integration (own TimescaleDB in Docker) | `services/api/tests/integration` | 315 | pass |
| Full stack (pipeline, importer) | `tests/integration` | 12 | pass |
| Processor failover smoke (kill 1 of 2 processors) | CI step, IT-02 after the kill | 1 | pass |
| Dashboard components | `services/dashboard/src` | 16 | pass |

## 2. Performance baseline (week 4)

Test cases PT-01, PT-02, PT-03 and PT-06, measured on a laptop. This is a baseline to find the bottlenecks early; the
official campaign runs on a fixed machine in week 8 (test plan 3.7).

### 2.1 How it was measured

`make baseline` (`tests/performance/baseline.py`) runs the load generator against the running stack at 100, 1,000 and
5,000 flows/s, 1 min warm-up and 5 min measured at every rate. The generated traffic is normal traffic from 200 clients
to 20 servers on 7 common ports, plus 5 % port scan flows from one source to one server.

- every 5 s: consumer lag of the processor and persister groups (newest offset minus committed offset) and
  `docker stats`
- lost flows: sent by the generator minus stored in `network_flows`
- late flows: flows the processor dropped because their window had already closed (its own counters)
- latency (NFR02): `created_at - last_ingested_at` of every detection, from the processor's "detection" log line, so
  it is measured when the detection is made. All detections made in the 5 measured minutes
- CPU in % of one core, memory per container

| Condition | Value |
|---|---|
| Date | 2026-11-03, 12:36 to 12:57 UTC |
| Code | commit `125061f` (detection engine #62, load generator #55), `detection.yaml` `8b8118e8cf18` |
| Machine | laptop, Intel Core i5-1135G7 (4 cores, 8 threads), 15.7 GB RAM, Windows 11 Pro (build 26200) |
| Docker | Docker Desktop 29.7.2, 8 CPUs and 7.6 GiB for Docker. Stack and load generator on the same machine and disk |
| Pipeline | 1 processor, 1 persister, `flows.raw` with 6 partitions, 1 load generator container |

### 2.2 Results

| Rate (flows/s) | Reached | Sent | Stored | Lost | Late (dropped) | Max lag processor / persister | Caught up after the load |
|---|---|---|---|---|---|---|---|
| 100 | 100 | 35,890 | 35,890 | 0 | 0 | 20 / 60 | 6 s |
| 1,000 | 997 | 359,100 | 359,100 | 0 | 4,730 (1.3 %) | 4,400 / 8,754 | 4 s |
| 5,000 | 4,974 | 1,791,000 | 1,791,000 | 0 | 84,348 (4.7 %) | 57,080 / 179,772 | 58 s |

Detection latency in seconds (no detections at 100 flows/s: the generated scan reaches 50 ports per 10 s, the
threshold is 100):

| Rate | Detections | Count | p50 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| 1,000 | all | 1,099 | 1.11 | 1.65 | 1.95 | 2.15 |
| | port scan (rule) | 99 | 0.06 | 0.11 | 0.18 | 2.03 |
| | abnormal traffic (z-score) | 1,000 | 1.15 | 1.71 | 1.95 | 2.15 |
| 5,000 | all | 798 | 1.02 | 1.24 | 1.34 | 5.80 |
| | port scan (rule) | 119 | 0.02 | 0.60 | 3.06 | 5.80 |
| | DoS (rule) | 79 | 0.12 | 0.15 | 1.37 | 1.73 |
| | abnormal traffic (z-score) | 600 | 1.02 | 1.24 | 1.34 | 1.34 |

| Rate | Processor CPU avg / max | Persister CPU avg / max | DB CPU avg / max | Max memory |
|---|---|---|---|---|
| 100 | 2 / 3 % | 2 / 2 % | 3 / 7 % | DB 972 MiB, Redpanda 679 MiB, others < 100 MiB |
| 1,000 | 5 / 6 % | 5 / 13 % | 19 / 78 % | DB 1,051 MiB, Redpanda 743 MiB |
| 5,000 | 21 / 44 % | 17 / 30 % | 82 / 119 % | DB 1,435 MiB, Redpanda 861 MiB, persister 165 MiB |

**Repeat.** The same ladder ran once before, at 12:10 UTC, with the first version of the script (its late flows and
the latency per type were read afterwards from the processor log of that run). At 5,000 flows/s:

| | Run 1 (12:10 UTC) | Run 2 (12:36 UTC, above) |
|---|---|---|
| Sent / lost | 1,796,000 / 0 | 1,791,000 / 0 |
| Late flows | 86,274 (4.8 %) | 84,348 (4.7 %) |
| Max lag processor / persister | 33,411 / 90,428 | 57,080 / 179,772 |
| Caught up after the load | 17 s | 58 s |
| Latency p95 / max | 1.12 s / 2.14 s | 1.24 s / 5.80 s |
| DB CPU avg / max | 81 / 102 % | 82 / 119 % |

At 1,000 flows/s run 1 had no late flows and a maximum lag of 300 / 701 messages.

### 2.3 What it shows

1. **100 and 1,000 flows/s are no problem.** Nothing is lost, the lag stays small and is gone a few seconds after the
   load, and no service uses more than a fifth of a core on average.
2. **Latency (NFR02, p95 at most 3 s at 5,000 flows/s): met on this laptop**, p95 1.12 to 1.24 s. The rules fire as
   soon as the threshold is crossed (port scan p50 0.02 to 0.06 s). The z-score method reports when its 60 s window
   closes, so it always carries the 1 s grace period of the windows (p50 about 1 s). The p99 of the port scan at
   5,000 flows/s (3.06 s) comes from the stalls in point 4.
3. **Throughput (NFR01, 5,000 flows/s for 5 min, lag must not grow): not met on this laptop.** The generator reaches
   the rate and nothing is lost, but the persister falls behind by up to 180,000 messages (about 36 s of data) and
   only catches up after the load stops. The database works at more than one core: every flow row updates 5 indexes,
   the write-ahead log forces a checkpoint about every minute, and in run 2 one disk sync took 11.8 s. Saturation is
   around 5,000 flows/s, limited by the database writes.
4. **Late flows: detections can be missed without an error.** Each window's clock also moves with the wall clock, so
   a window closes even when its flows are only delayed. When the processor got its flows more than 1 to 2 s late
   (here during the disk stalls), those flows arrived after their window had closed and were dropped from detection.
   They are still stored, so nothing is lost in the database, but no rule saw them: 4.7 to 4.8 % at 5,000 flows/s,
   1.3 % at 1,000 flows/s in run 2. The latency numbers don't show this, because a dropped flow never becomes a
   detection.
5. **Two effects of the generated traffic, not of the system.** Every rate step makes all 200 clients deviate from
   their own history, so the z-score method reports each of them once per 60 s window (1,000 abnormal traffic
   detections at 1,000 flows/s = 200 clients x 5 windows). That is still worth knowing for false alarms (DQ-02): when
   the whole network gets busier, every host looks abnormal. And at 5,000 flows/s one server gets about 490
   connections/s from more than 10 sources (normal traffic plus the scan), right at the DDoS-like threshold of 500/s,
   so 79 DoS detections show up.
6. **The `detection_latency` view** gives the same numbers as the processor on the same window, except for escalated
   detections, which get a negative latency there (29 at 5,000 flows/s). Fixed in #65.

### 2.4 Next steps

- Persister and database (M3, M5): batch inserts with `COPY`, check which of the 5 indexes on `network_flows` are
  really needed (the primary key on `flow_id` and the `trace_id` index get random values, the most expensive kind),
  a larger `max_wal_size` (now the default 1 GB) so checkpoints follow the time and not the WAL volume. Then measure
  5,000 flows/s again.
- Processor (M2): a window should not close while the processor is behind, a delayed flow should wait instead of being
  dropped. And the z-score reaction to a network-wide change.
- Week 8 campaign on a desktop machine (PT-01 to PT-06): up to 10,000 flows/s and more, and 3 processor instances
  (PT-04).

### 2.5 Test cases

| ID | Scenario | Expected | Actual | Status | Comment |
|---|---|---|---|---|---|
| PT-01 | 100, 1,000, 5,000 flows/s, 1 processor | throughput, lag and resources per rate, saturation point | stable at 100 and 1,000; at 5,000 nothing lost but the lag grows | baseline done | saturation around 5,000 flows/s on the laptop, database bound |
| PT-02 | 5,000 flows/s for 5 min | lag does not grow, nothing lost | nothing lost; persister lag up to 180,000 messages; 4.7 % late flows | fail | laptop; re-test after the persister changes and in week 8 |
| PT-03 | latency at 5,000 flows/s | p95 at most 3 s | p95 1.24 s, rules p50 0.02 s | pass (indicative) | official run in week 8; late flows are not in this number |
| PT-06 | CPU and memory per container | reported, no container at its limit | database 82 % of a core on average, 1.4 GiB; the rest below 45 % of a core | pass (baseline) | compose sets no memory limits; total far below the 7.6 GiB of Docker |

## 3. Defects found

| Found | Defect | Effect | Status |
|---|---|---|---|
| week 1 | one malformed message on `flows.raw` stops the consumers (#8, RT-06) | pipeline stops | processor skips it since #62, persister still open |
| week 4, baseline | escalated detections get a negative latency in `detection_latency` | NFR02 can't be read from the database | fix in #65 |
| week 4, baseline | flows that reach the processor late are dropped, the window clock moves with the wall clock | detections missed under load, without an error | open (M2) |
| week 4, baseline (seen once) | after the broker container was recreated, the processor stayed at 0 flows while the persister recovered | processing stops after a broker outage | to check with RT-05 in week 8 |
| week 4, baseline | persister and database don't keep up with 5,000 flows/s on the laptop | NFR01 | open (M3, M5), risk R1 |
