# Architecture Document - Detection Engine (M2)

> Owner: Kuzma (M2, Anomaly Detection & Algorithms)
> Covers: `services/processor/` (stream processor + `detection_engine/`), `config/detection.yaml`, the
> detection contract (`detection.v1.json`) from the producer side, and which detections become alerts.
> Spec sections 6 (steps 7-9), 8, 9, 18 ("detection algorithms and time windows"); F05-F09, F17, NFR01-NFR04.

## 1. Responsibility

The processor consumes normalised flows from `flows.raw`, groups them into 1 s, 10 s and 60 s windows, computes
the window features, runs the four rules and the statistical method, gives every result a type, severity,
confidence and explanation, decides whether it raises an alert, and publishes it to `detections`. It never
reads the database and never reads the ground-truth `label`.

All the logic is in `services/processor/detection_engine/`, a package without broker or database code, so it is
tested directly (`tests/unit/test_detection_engine.py`). `processor.py` only connects it to the broker.

| Module | What |
|---|---|
| `config.py` | loads and checks `detection.yaml`; invalid or missing value -> `ConfigError`, the processor does not start (UT-17) |
| `windows.py` | tumbling windows over flow time, per-key event clock, per-window features |
| `rules.py` | port scan, DoS-like, brute force, abnormal connection pattern |
| `statistical.py` | second method: per-source z-score against the source's own history |
| `scoring.py` | severity from the ratio, confidence |
| `alerting.py` | which detections become alerts (severity threshold, cooldown, escalation) |
| `engine.py` | runs everything per batch and builds the `detection.v1` messages |

## 2. Data flow

```
flows.raw (key = src_ip)
   |  consume a batch (poll_batch)
   v
engine.add(flow)          -> source windows 1/10/60 s (key src_ip) + target windows (key dst_ip, DoS window)
engine.evaluate(now)
   1. close windows whose time is over -> rules + statistical method -> learn history / profiles
   2. evaluate windows that got flows   -> rules (fire as soon as a threshold is crossed)
   3. severity + confidence + explanation -> alert policy -> detection.v1 (+ alert flag)
   |
   v
detections (key = detection_id) -> persister -> detections table (+ alerts table when alert = true)
```

## 3. Time windows (F05)

**Tumbling windows** of 1, 10 and 60 s, aligned to multiples of their size (`[start, start + size)`). Every flow
goes into one window of each size. Tumbling, not sliding: every flow is counted once per size, a detection has
one well-defined window (part of the deterministic `detection_id`), and the cost per flow is constant. A burst that
straddles a boundary is split in two halves and can stay below the threshold in both; test case DQ-06 measures
how often that happens, and if it matters a hopping 10 s window (every 5 s) is the fix.

**Which rule uses which window** (configurable): DoS 1 s (floods are short and intense), port scan 10 s, brute
force, abnormal connection pattern and the statistical method 60 s (slower behaviour needs more evidence).

**Flow time, not wall time.** Windows use `ts_start`, so a PCAP replayed today is analysed with its original
timing, the same as live simulator traffic (deployment doc section 8).

**Event clock per key.** A window closes when its key's clock passes `end + grace_s` (1 s). The clock of a key is
the newest `ts_start` seen for it, moved forward by the wall-clock time since its last flow, so the last window of a
source that went quiet still closes. It is one clock per key, not one per processor, because:

- flows of one source arrive in order (one partition), so the source's own clock is reliable;
- during a fast import, different partitions can be minutes apart in flow time. One global clock would close the
  windows of the slower partitions and drop their flows as late.

A flow for a window that has already closed is **late**: counted (`late_flows` in the periodic `engine stats` log
line) and not added to that window, but still added to the longer windows that are still open.

## 4. Features (spec 8, F03)

Per source and window: flows (= connections per window), packets, bytes, unique destination ports, unique
destination hosts, connections and packets per destination, attempts per (destination, login port), and new
destinations compared with the source's profile (new-connection rate). Per target and DoS window: connections,
packets, connections per source. Packets/s and bytes/s are the window values divided by the window size.

## 5. Rule-based detection (F06, spec 9.1)

Deterministic: a rule fires when `observed >= threshold` in its window. Thresholds are in `detection.yaml`
(first estimates; the threshold sweep DQ-04 in week 5 sets the final values).

| Type | Window | Observed feature | Default threshold | Source / destination |
|---|---|---|---|---|
| `port_scan` | 10 s | distinct destination ports of one source | 100 | src / dst if only one host |
| `dos` (one source) | 1 s | connections **or** packets from one source to one target, whichever is further above its threshold | 500 connections / 20,000 packets | src / dst |
| `dos` (DDoS-like) | 1 s | same, summed over all sources of one target, at least `ddos_min_sources` (10) sources | same | null / dst |
| `brute_force` | 60 s | connection attempts from one source to one (host, login port), ports 22, 3389, 21, 23 | 50 | src / dst, port in features |
| `suspicious_pattern` | 60 s | hosts the source contacted that are not in its connection profile (hosts contacted in the last 600 s) | 50 | src / null |

`suspicious_pattern` is the spec's **Abnormal Connection Pattern** ("significant deviation from the baseline
connection profile"). It compares a source with its own profile instead of a global number, so a client that
always talks to the same 20 servers never triggers it, but the same client suddenly reaching 60 new hosts does. It
counts new hosts, not new (host, port) pairs, so a port scan of one host does not also count as this class. The
profile keeps at most 5,000 hosts per source.

**Early firing.** Rules are evaluated on every batch for every window that got new flows, not only when the window
closes. A detection is created as soon as the threshold is crossed, so latency (NFR02, `created_at -
last_ingested_at`) does not include waiting for the window to end (Conventions section 4).

**Escalation.** A scan that keeps going after its first detection gets a higher ratio. The engine sends the
detection again, with the same `detection_id` and the higher severity, each time it reaches a new severity level
(at most four messages per detection, never two at the same level). The persister keeps the highest severity and
the original `created_at` (section 9).

## 6. Second method: z-score (F07, spec 9.2)

**Method.** For every source we keep the features of its last `baseline_window_s / window_s` = 10 closed 60 s
windows (a quiet minute counts as zeros). A closed window is scored per feature as
`z = (value - mean) / std`. To stop a very steady history (std about 0) from turning a single extra flow into a
huge z, `std` has a floor of `max(sqrt(mean), 0.1 * mean, 1)`, which is the natural spread of a random count.

| Highest z >= `zscore_threshold` (3.0) in | Type |
|---|---|
| volume: flows, packets, bytes | `abnormal_traffic` (significant deviation from the historical traffic level) |
| only structure: unique ports, unique hosts | `unknown` (anomalous, but matches no known class) |

- No result before `min_baseline_windows` (10) windows of history, so the first 10 minutes of a source only learn.
- A window that scored as anomalous, or in which a rule fired, is **not** added to the history, so an attack
  does not become the new normal.
- A source quiet for longer than the whole history starts over, because a history of zeros would flag any traffic.
- Runs on closed windows only. Latency stays low because for ongoing traffic `last_ingested_at` is close to the
  window end.

**Why z-score per source** (and not Isolation Forest, which `detection.yaml` keeps open as an option): it needs
no training data set and no extra library, it adapts per host, it can be explained in one sentence ("120 flows,
usually 30 +- 6, z = 15"), and it is cheap enough for 5,000 flows/s. The weakness is that it only sees the
features one at a time and needs a warm-up per source.

**Rules first.** If a rule fired for a source in a period that overlaps the statistical window, the statistical
result for that window is dropped: a known class says more than "the source changed", and without this rule a
port scan would also count as a false positive for `abnormal_traffic` in the per-class metrics.

**Comparison with the rules** (spec 9.2), planned for the week 5 quality run: per class precision/recall of both
methods on SIM-SCEN (abnormal traffic: z-score vs. the volume-ratio idea of the rules), false alarms on SIM-NORMAL,
and the warm-up cost. For this run the engine needs a switch that turns the "rules first" filter off, so both
methods are measured on the same data (to add in week 5).

## 7. Severity and confidence (F08, spec 9.3)

`ratio = observed / threshold` (`z / zscore_threshold` for the statistical method), so 1.0 = just crossed.
Severity = the highest level in `detection.yaml` whose value is `<= ratio`:

| LOW | MEDIUM | HIGH | CRITICAL |
|---|---|---|---|
| >= 1.0 | >= 1.5 | >= 3.0 | >= 5.0 |

Confidence is how sure we are of the class, not how bad the event is: `min(ceiling, base + 0.1 * ratio)` with
(base, ceiling) = (0.5, 1.0) for rules, (0.4, 0.9) for `abnormal_traffic` and (0.3, 0.7) for `unknown`. A rule
checks the exact behaviour of its class, a z-score only says that a source changed, and `unknown` has no class at
all. These are first estimates; DQ-01 checks whether high confidence really means fewer false positives.

## 8. Explainability (F09)

Every detection carries the evidence an operator needs without opening the raw flows:

- `features`: the observed key values, the `threshold`, the `ratio` and, for the z-score, `baseline_mean`,
  `baseline_std`, `zscore`, `baseline_windows` and which `feature` triggered;
- `window` (size, start, end), `src_ip` / `dst_ip`;
- `explanation`, one sentence with the same numbers, e.g. *"10.66.6.6 contacted 300 distinct destination ports
  on 1 host(s) in 10 s (threshold 100). 3.0x the threshold -> HIGH."*;
- `trace_ids`: up to 20 trace IDs of contributing flows (F15), to follow a detection back to its input.

## 9. Which detections become alerts (F17)

Every detection is stored and visible in the history. An **alert** is the part an operator has to look at and
acknowledge. Raising one for every detection would bury the operator (a 2-minute port scan = 12 detections), and
the spec asks to "reduce false alarms" (section 2). DQ-02 even sets a limit: at most 2 alerts per 10 minutes of
normal traffic, and no HIGH/CRITICAL. The policy is in `detection.yaml`:

```yaml
alerts:
  min_severity: MEDIUM     # LOW = just above the threshold, where most false positives are
  min_severity_by_type:
    unknown: HIGH          # the class with the least evidence behind it
  cooldown_s: 300
```

1. **Severity threshold.** A detection raises an alert only from `min_severity` (MEDIUM, ratio >= 1.5). A LOW
   detection is 1.0-1.5x its threshold: that is where normal traffic peaks are, and where a threshold set a bit too
   low produces noise. Such detections are still stored and counted in the quality metrics. `unknown` needs HIGH
   (z >= 9), because nothing but the deviation supports it.
2. **Cooldown.** At most one alert per (type, source, destination) per 5 minutes of flow time. One attack that
   lasts several windows gives one alert; the alert links to the first detection, and the history shows all of them.
3. **Escalation.** Inside the cooldown, a detection with a **higher** severity than the last alert raises a new
   alert (a scan that turns from MEDIUM into CRITICAL is news). The same detection escalating inside its window
   keeps its single alert.

**Where it runs.** The decision is made in the processor and sent as `alert: true/false` in the detection message
(optional field of `detection.v1`, missing = false). The cooldown needs state per source, and the processor is the
only place where all detections of one source pass through the same instance (flows keyed by src_ip). The
persister writes the alert row (`status = 'NEW'`, `alert_id = uuid5(detection_id)`, `ON CONFLICT (detection_id)
DO NOTHING`) in the same transaction as the detection. So the "Alert & Classification Service" of the spec
reference architecture is split: the policy is in the processor (M2), alert storage and the acknowledge workflow are
in the persister and the API (M3).

Measured on the simulator (`normal,port_scan`, 1,000 flows/s, 12 min of flow time): normal traffic 0 detections;
one continuous port scan gave 72 detections and 6 alerts, one per cooldown period plus an escalation to CRITICAL in
each. That scan sits right at the CRITICAL boundary (about 500 ports per window); week 5 checks whether the
escalation should compare with the highest severity seen during the cooldown instead of the last alert.

## 10. Contract changes

| Change | Why | Compatible? |
|---|---|---|
| `alert` (optional boolean) in `detection.v1.json` | carries the alert decision to the persister | yes: missing = false, `schema_version` stays 1 |
| same `detection_id` sent again with a higher severity | early firing + escalation | the persister upserts: updates severity, confidence, features, explanation, trace IDs and `last_ingested_at` **only** if the new severity is higher; `created_at` stays, so latency is measured to the first detection and an older redelivered message never downgrades a row |

## 11. Scalability and resilience (NFR01, NFR03, NFR04)

- **Throughput.** On the simulator's traffic the engine alone handles about 56,000 flows/s in one process
  (laptop, Python 3.11), more than ten times NFR01. The broker client and JSON decoding cost more than the
  detection; PT-01 measures the whole processor.
- **Several instances.** All source state (windows, history, profile, cooldown) is keyed by src_ip, and flows are
  partitioned by src_ip, so instances never need each other's state.
- **Limitation, DDoS-like check:** target windows only count the sources of the instance's own partitions. With
  one instance the check is exact; with N instances each sees about 1/N of a distributed flood. A fast import
  that keeps the partitions far apart in flow time can also make target-window flows late (the clock of a target
  follows all its sources). The fix, if PT-04/RT-01 show it matters, is a second stage keyed by dst_ip (a
  `flows.by_dst` topic or aggregated partial counts).
- **Restart.** Windows, histories and profiles are in memory. A restarted or reassigned instance loses at most one
  window of evidence and has to rebuild the statistical history (10 min warm-up per source). Offsets are committed
  before windows close (see `processor.py`), so a crash can also lose the flows of the open windows. A state store
  or replay from the window start offsets is the planned fix (week 8, RT-01/RT-02).
- **Bad input.** A flow without a needed field is skipped and logged as WARNING; the engine checks the fields before
  changing any window. Late flows are counted.
- **Memory.** Per-source state of sources quiet for longer than it is used (history, profile, cooldown) is removed
  every 60 s.

## 12. Configuration (F16, spec 9.1)

`config/detection.yaml` holds every default. The processor reads it at start (`DETECTION_CONFIG`) and checks it
completely: every key present, types, positive thresholds, every `window_s` one of `windows_s`, `windows_s`
containing 1, 10 and 60, severity levels increasing, `min_baseline_windows` fitting in the baseline, known
types and levels in `alerts`. On any error it logs the field and exits (code 2), so a typo never silently turns a
rule off (UT-17).

Changing thresholds at runtime (F16 in the vision document, API-07) is not implemented yet. Plan (week 6, with
M3): the API stores the new parameters in `detection_configs` and publishes a small control message; every
processor instance validates it with the same `parse_config()` and swaps its `DetectionConfig` between two
batches. Open windows keep their counts, so the new thresholds apply immediately.

## 13. Tests

| Test plan ID | What | Where |
|---|---|---|
| UT-06, UT-13 | window close after size + grace, flows on boundaries, late flows, per-source clock, old PCAP time | `tests/unit/test_pipeline_logic.py`, `test_detection_engine.py` |
| UT-07, UT-08, UT-09 | port scan with evidence, normal traffic silent, same input -> same `detection_id` | `test_pipeline_logic.py` |
| UT-14 | DoS (connections, packets, DDoS-like), brute force, abnormal connection pattern: fire above, silent below | `test_detection_engine.py` |
| UT-15 | z-score: no result before the baseline, abnormal traffic, unknown, rule precedence, restart after silence | `test_detection_engine.py` |
| UT-16 | severity table from the config, confidence range and order | `test_detection_engine.py` |
| UT-17 | invalid / missing config values | `test_detection_engine.py` |
| F17 (unit part of IT-08) | severity threshold, `unknown` needs HIGH, cooldown, escalation, alert flag on escalation, persister alert row and upsert | `test_detection_engine.py`, `test_persister_alerts.py` |
| DQ-07 | labels removed -> same detections | `test_detection_engine.py` |

## 14. Key decisions

| Decision | Alternatives | Why |
|---|---|---|
| Tumbling windows | sliding / hopping windows | one window per flow per size, deterministic detection IDs, constant cost; boundary misses measured in DQ-06 |
| Flow time with a clock per key | wall clock; one watermark per instance | PCAP replay keeps its timing; partitions of a fast import do not make each other late |
| Fire on crossing + escalate | fire when the window closes | NFR02: no waiting for the end of a 60 s window |
| Per-source z-score | Isolation Forest, global z-score | no training set, explainable, per-host baseline, cheap |
| Rules before the statistical method | report both | the per-class metrics would count every rule hit twice |
| Alert policy in the processor | in the persister / API | the cooldown needs per-source state, which only the processor has consistently |

## 15. Open points

- Final thresholds, confidence parameters and the std floor: threshold sweep and quality run (DQ-01..04, week 5).
- Whether escalation inside the cooldown should compare with the highest severity seen in it (section 9).
- Runtime configuration change (F16, API-07), with M3, week 6.
- DDoS-like check across instances and state after restart (section 11), weeks 8.
- The simulator scenarios for DoS, brute force and the abnormal connection pattern arrive in week 4 (M1); until
  then the rules are only tested with unit-test traffic.
