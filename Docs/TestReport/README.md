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

## 3. Detection quality (week 5)

Test cases DQ-01 to DQ-04, DQ-06 and DQ-08 (test plan 3.6): the first measurement on real attacks, with the default
thresholds of `config/detection.yaml` from #62. Nothing was tuned before this run, it is the starting point for the
tuning in week 6. DQ-05 (held-out part of the dataset) follows in week 9.

### 3.1 How it was measured

Three labelled files and one normal-only file, converted from CIC-IDS2017 with `convert_cic.py` (#63, how to get them:
[dataset section of the architecture document](../ArchitectureDocument/dataset/README.md)). Each has its ground-truth
manifest next to it. The CSV files are too big for the repository (`data/flows/cic*.csv` is ignored), the manifests
are in it.

| File | Part of the dataset | Flows | Flow time | Episodes for recall | Left out (< 10 flows) |
|---|---|---|---|---|---|
| `cic-friday-portscan.csv` | Friday afternoon, PortScan | 286,431 | 2.5 h | 5 port scans | 3 (7, 1 and 2 flows) |
| `cic-tuesday-bruteforce.csv` | Tuesday, FTP-Patator and SSH-Patator | 445,892 | 8.1 h | 2 brute force | 1 (1 flow) |
| `cic-friday-ddos.csv` | Friday afternoon, DDoS LOIT | 225,743 | 1.5 h | 1 DoS | 1 (3 flows) |
| `cic-monday-normal.csv` | Monday 09:00 to 09:30, all BENIGN | 30,352 | 31 min | none | - |

The episodes left out are stray labels, a few flows with an attack label away from the attack (for example one
PortScan flow at 13:52, the scans start at 13:55). They don't count for recall, but a detection that hits them still
counts as correct (`--min-flows 10`, added to 3.6 of the test plan).

Full stack, a fresh stack for every file (own Compose project, volumes removed before each file):

1. import the file without replay (`docker compose --profile import run --rm importer`), so the detections keep the
   flow time of the file
2. wait until the processor and persister groups have no lag, wait 75 s for the last 60 s windows, check the lag again
3. `python tests/quality/evaluate.py data/flows/<file>.csv --min-flows 10`
4. for the normal file also the alerts: the `alerts` table joined with the detections

Threshold sweep: `tests/quality/sweep.py` (new) runs the detection engine of the processor directly on a file. Same
code and config, batches of 500 flows, a clock that moves at the import speed (about 11,400 flows/s), one row per
detection with its highest severity like the persister, and the scoring of `evaluate.py`. One value takes about 15 s
instead of a stack run. At the default config it gives the same detections as the stack: identical on the port scan
and normal files, 3 more out of 3,549 on the Tuesday file, one with another type on the DDoS file (the stack drops
some flows as late, point 6 in 3.5). On the normal file it also applies the alert policy and counts the alerts.

```
python tests/quality/sweep.py data/flows/cic-friday-portscan.csv rules.port_scan.unique_dst_ports_threshold \
    5 10 20 50 100 200 --normal data/flows/cic-monday-normal.csv --min-flows 10
```

The other tables in 3.4 are the same command with the file and parameter named above them.

| Condition | Value |
|---|---|
| Date | full stack 2026-11-08, 22:57 to 23:15 UTC; alerts on the normal file and the sweeps 2026-11-09 |
| Code | commit `b9d8ef5` (main after #70), `detection.yaml` `8b8118e8cf18` (the same as in the week 4 baseline) |
| Machine | the laptop of 2.1, Docker Desktop with 8 CPUs and 7.6 GiB |
| Pipeline | 1 processor, 1 persister, `flows.raw` with 6 partitions |

### 3.2 Results at the default thresholds (DQ-01, DQ-03)

| File | Class | Episodes | Detections | Precision | Recall | F1 | Detections per found episode |
|---|---|---|---|---|---|---|---|
| Friday port scan | port_scan | 5 | 62 | 1.00 | 0.60 | 0.75 | 21 on average, 34 at most |
| Tuesday brute force | brute_force | 2 | 122 | 1.00 | 1.00 | 1.00 | 61 |
| Friday DDoS | dos | 1 | 0 | - | 0.00 | 0.00 | - |

Macro F1 over the three classes with labelled episodes: 0.58 (target 0.80). CIC-IDS2017 has no episodes for
`abnormal_traffic` and `suspicious_pattern`, so their recall can't be measured and every detection of them counts as
false.

Confusion matrix of the three attack files together (DQ-03). Rows: the real class of every episode, counted once for
every predicted class that hit it; "normal" is the detections that hit no episode at all.

| Real \ predicted | port_scan | dos | brute_force | abnormal_traffic | suspicious_pattern | unknown | missed |
|---|---|---|---|---|---|---|---|
| port_scan (5) | 3 | 1 | 0 | 2 | 0 | 0 | 2 |
| dos (1) | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| brute_force (2) | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| normal | 56 | 22 | 0 | 4,552 | 247 | 160 | - |

The detections that hit no episode are 418, 421 and 366 per hour of data on the three files.

Misses and wrong classes:

- port_scan-003 and -004 (226 and 138 flows): nmap runs that only touch 5 ports, again and again. No detection at
  all. A rule that counts ports can't tell them from normal traffic (3.4)
- dos-001, the DDoS (128,024 flows in 20 min): the three attacking machines are behind NAT and show up as one address,
  172.16.0.1, with about 100 connections per second to the web server (187 in the busiest second). The DoS rule needs
  500 in one second, and the DDoS-like check per target needs 10 sources. Only an `unknown` of the z-score hit it
- 176 DoS detections during port_scan-005: the fast scan makes more than 500 connections per second to one host, so
  the DoS rule fires next to the port scan rule. They count as false positives for DoS

### 3.3 Normal traffic (DQ-02)

31 minutes of Monday traffic, all labelled BENIGN: 140 detections (271 per hour) and 61 alerts after the alert policy,
19.7 per 10 minutes, 39 of them HIGH or CRITICAL. The target is at most 2 alerts per 10 minutes and none HIGH or
CRITICAL. Where they come from (checked in the flows):

| Type | Detections | Alerts | HIGH/CRITICAL alerts | Cause |
|---|---|---|---|---|
| abnormal_traffic (z-score) | 106 | 50 | 36 | mostly bytes (69 of the 118 statistical detections) and packets (25): one large transfer against the quiet history of a workstation |
| unknown (z-score) | 12 | 0 | 0 | jump in distinct ports or hosts; `unknown` needs HIGH for an alert |
| suspicious_pattern | 12 | 6 | 0 | workstations contacting 50 to 120 new hosts in a minute, normal web browsing |
| dos | 7 | 4 | 3 | one workstation downloading from a Microsoft update server: flows of 120 s with up to 511,681 packets, all counted in the second where the flow starts |
| port_scan | 3 | 1 | 0 | flows recorded the wrong way round: an HTTPS server (source port 443) "contacts" 213 client ports in 10 s |

### 3.4 Threshold sweep (DQ-04)

One parameter at a time, the rest at the default. Precision, recall and F1 of the class on its attack file, and the
false detections of the same class per hour on the normal file.

Port scan, `unique_dst_ports_threshold` (10 s window), Friday port scan file:

| Threshold | Detections | Precision | Recall | F1 | Normal: false port scans per hour |
|---|---|---|---|---|---|
| 5 | 798 | 0.11 | 1.00 | 0.19 | 276.9 |
| 10 | 142 | 0.44 | 0.60 | 0.51 | 31.0 |
| 20 | 89 | 0.70 | 0.60 | 0.64 | 11.6 |
| 50 | 65 | 0.95 | 0.60 | 0.74 | 7.7 |
| 100 (default) | 62 | 1.00 | 0.60 | 0.75 | 5.8 |
| 200 | 62 | 1.00 | 0.60 | 0.75 | 3.9 |

DoS, Friday DDoS file: `connections_to_target_threshold` in the 1 s window, then `window_s` with the threshold of 500:

| Threshold | Window | Detections | Precision | Recall | F1 | Normal: false DoS per hour |
|---|---|---|---|---|---|---|
| 50 | 1 s | 1,174 | 0.74 | 1.00 | 0.85 | 71.7 |
| 100 | 1 s | 1,058 | 0.77 | 1.00 | 0.87 | 17.4 |
| 150 | 1 s | 517 | 0.79 | 1.00 | 0.88 | 13.6 |
| 200 and 300 | 1 s | 0 | - | 0.00 | 0.00 | 13.6 |
| 500 (default) | 1 s (default) | 0 | - | 0.00 | 0.00 | 13.6 |
| 500 | 10 s | 110 | 0.82 | 1.00 | 0.90 | 13.6 |
| 500 | 60 s | 46 | 0.52 | 1.00 | 0.69 | 32.9 |

Brute force, `attempts_same_service_threshold` (60 s window), Tuesday file:

| Threshold | Detections | Precision | Recall | F1 | Normal: false brute force per hour |
|---|---|---|---|---|---|
| 5 | 172 | 0.73 | 1.00 | 0.84 | 1.9 |
| 10 and 20 | 125 | 1.00 | 1.00 | 1.00 | 0 |
| 50 (default) | 122 | 1.00 | 1.00 | 1.00 | 0 |
| 100 | 83 | 1.00 | 1.00 | 1.00 | 0 |
| 200 | 0 | - | 0.00 | 0.00 | 0 |

Suspicious pattern and the z-score method have no labelled episodes, so only their false alarms on the normal file:

| `new_dst_ips_threshold` | Normal: false detections per hour | Detections on the port scan file |
|---|---|---|
| 50 (default) | 23.2 | 59 |
| 100 | 5.8 | 9 |
| 200 | 0 | 1 |

| `zscore_threshold` | Normal: abnormal_traffic per hour | Normal: unknown per hour | All alerts per 10 min | HIGH/CRITICAL alerts |
|---|---|---|---|---|
| 3 (default) | 205.3 | 23.2 | 19.7 | 39 |
| 4 | 129.7 | 5.8 | 14.8 | 28 |
| 5 | 114.3 | 3.9 | 14.2 | 21 |
| 6 | 106.5 | 1.9 | 12.9 | 22 |
| 8 | 81.3 | 0 | 11.9 | 20 |
| 10 | 69.7 | 0 | 9.7 | 17 |
| 15 | 42.6 | 0 | 8.1 | 11 |

With the DoS window at 10 s and the suspicious pattern threshold at 200 as well (`--set`): 18.7 alerts per 10 minutes
at a z-score threshold of 3, 8.4 at 10, 6.1 at 15 and still 3.9 with 7 HIGH/CRITICAL at 30.

### 3.5 What it shows

1. **Port scan and brute force work on real attacks.** Precision 1.00 for both. Brute force finds both attacks with
   any threshold from 10 to 100 and has no false alarms on the normal file, so the default of 50 is in the middle of a
   safe range. The port scan rule finds every scan that goes through the ports (998 to 1,000 ports). The two misses
   touch only 5 ports, and a threshold low enough for them gives 277 false port scans per hour. The default of 100 is
   justified, 200 keeps the same recall with fewer false alarms (3.9 instead of 5.8 per hour).
2. **The DDoS is missed by the DoS rule.** One NAT address, about 100 connections per second, and a threshold of 500
   per second. A 10 s window with the same threshold (50 per second on average) finds it with the best F1 (0.90) and
   no more false DoS on the normal file than now. 150 per second in the 1 s window also finds it, but with little
   margin (200 already misses it), and the dataset only has timestamps to the minute, which the converter spreads over
   the minute, so the real peaks per second are not known. A 10 s window depends less on that.
3. **False alarms are the main problem.** About 20 alerts per 10 minutes on normal traffic, ten times the target, two
   thirds of them HIGH or CRITICAL, and 270 to 420 detections per hour on every file.
   - the z-score method makes most of them: the bytes and packets of one large transfer are many standard deviations
     above the quiet history of a workstation. A higher threshold alone doesn't fix it: at 15 there are still 8.1
     alerts per 10 minutes with 11 HIGH/CRITICAL. The method needs a change, for example the z-score of log(bytes) and
     log(packets) instead of the raw values, and a minimum increase before a window counts as abnormal
   - the packet check of the DoS rule counts all packets of a flow in the second where the flow starts, so a 2-minute
     download becomes a CRITICAL DoS. Spreading the packets over the duration of the flow would fix it
   - suspicious pattern: 50 new hosts per minute is normal web browsing. 200 removes all false ones on the normal file
     (there is no labelled attack of this class to see what it would miss)
4. **A fast scan is also a DoS.** All 176 DoS detections of the port scan file are the scanner during port_scan-005.
   The DoS check could skip a source that the port scan rule already reported for the same time.
5. **Some flows are recorded the wrong way round in the dataset.** CICFlowMeter sometimes starts a flow with the
   server's packet: the false port scan on the normal file is an HTTPS server "scanning" its clients' ports, and with
   the DoS threshold at 150, 92 of the 111 false DoS detections are the DDoS seen from the victim to the attacker. The
   matching of 3.6 counts them as false, counted as the attack the DoS precision at 150 would be 0.96. Whether the
   converter should turn such flows around (well-known source port, ephemeral destination port) is to be decided
   before the final run.
6. **Late flows at import speed.** The stack dropped 0.3 to 1.3 % of the flows as late (`late_flows` of the processor:
   1,346, 5,217, 562 and 395 for the four files) without any stall, the offline run of the same files drops none. The
   detections differ by at most 3 per file, so the results above hold, but it is the late-flow defect of week 4 (2.3,
   point 4) again: during an import the flow time runs hundreds of times faster than the wall clock, so a short pause
   of the processor, or two partitions read a little apart, already closes windows.
7. **Hard cases (DQ-06)**, as unit tests in `tests/unit/test_detection_hard_cases.py`: a scan of 120 ports split over
   two 10 s windows (60 + 60) is missed, so tumbling windows can miss a scan of up to twice the threshold; 99 new ports
   in every 10 s window for a minute is missed; a slow scan (one new port per second) from a host with a history is
   reported as `unknown` by the z-score; a 150-port scan inside 2,000 normal flows to the same server is found.
8. **Content of the detections (DQ-08).** All 5,545 detections of the four files are valid detection.v1 messages
   with the observed values, threshold and ratio (and the z-score for the statistical method), window, source or
   destination, severity, confidence and explanation (`tests/quality/check_content.py`, no problems found).

### 3.6 Next steps

- Detection engine (M2): the proposals of points 2 to 4 (DoS window of 10 s, packets of a flow spread over its
  duration, no DoS for a source already reported as a port scan, suspicious pattern threshold around 200, z-score on
  log values with a minimum increase). Then the same sweeps and a full-stack run again in week 6.
- Data (M1, M5): more than one DoS episode, so DoS recall isn't decided by a single attack (the Wednesday file of
  CIC-IDS2017 has DoS Hulk, GoldenEye, slowloris and Slowhttptest); the flow direction (point 5); labelled data for
  `suspicious_pattern` and `abnormal_traffic` from our own small captures.
- Evaluation (M5): IT-04 with one sample of every class through the stack (week 6), DQ-05 on a held-out part in week 9.

### 3.7 Test cases

| ID | Scenario | Expected | Actual | Status | Comment |
|---|---|---|---|---|---|
| DQ-01 | precision, recall, F1 per class on three CIC-IDS2017 files | port scan, DoS and brute force P and R >= 0.90, macro F1 >= 0.80 | port scan P 1.00 R 0.60, DoS R 0.00, brute force P 1.00 R 1.00, macro F1 0.58 | fail | default thresholds; the DDoS and two 5-port scans missed; re-run in week 6 after tuning |
| DQ-02 | 31 min of normal traffic (Monday) | no HIGH/CRITICAL alert, at most 2 alerts per 10 min | 19.7 alerts per 10 min, 39 HIGH/CRITICAL | fail | z-score method, DoS packet count of long flows |
| DQ-03 | confusion matrix with `unknown` | reported, errors analysed | 3.2, 3.3 and 3.5 | pass | no labelled episodes for 2 of the 5 classes |
| DQ-04 | threshold sweep for every rule and the z-score | default thresholds justified by the results | port scan and brute force justified; DoS misses the DDoS; suspicious pattern and z-score too sensitive | done, 3 defaults to change | `tests/quality/sweep.py`, proposals in 3.5 |
| DQ-06 | split scan, scan just below the threshold, slow scan, scan in heavy traffic | behaviour documented, misses explained | split scan and 99 ports per window missed, slow scan found as `unknown`, scan in heavy traffic found | pass | `tests/unit/test_detection_hard_cases.py` |
| DQ-08 | content of every detection | features, threshold or deviation, window, source/destination, severity, confidence | all 5,545 detections complete | pass | `tests/quality/check_content.py` |

## 4. Defects found

| Found | Defect | Effect | Status |
|---|---|---|---|
| week 1 | one malformed message on `flows.raw` stops the consumers (#8, RT-06) | pipeline stops | processor skips it since #62, persister still open |
| week 4, baseline | escalated detections get a negative latency in `detection_latency` | NFR02 can't be read from the database | fix in #65 |
| week 4, baseline | flows that reach the processor late are dropped, the window clock moves with the wall clock | detections missed under load, without an error | open (M2) |
| week 4, baseline | persister and database don't keep up with 5,000 flows/s on the laptop | NFR01 | open (M3, M5), risk R1 |
| week 5, detection quality | the DoS rule counts all packets of a flow in the second where the flow starts | a long download is a CRITICAL DoS (DQ-02) | open (M2) |
| week 5, detection quality | a fast port scan also fires the DoS rule | 176 wrong DoS detections next to the port scan (DQ-01) | open (M2) |
| week 5, detection quality | the z-score method compares raw bytes and packets with the history of a source | about 200 false detections per hour on normal traffic, most of them HIGH/CRITICAL (DQ-02) | open (M2) |
| week 5, CIC-IDS2017 data | some flows are recorded server -> client | false port scan on normal traffic, the DDoS also seen from the victim (DQ-01) | to decide (M1, M5) |
