# Test dataset: CIC-IDS2017 (M1)

> Owner: Valeriia (M1). Covers: `services/importer/convert_cic.py`,
> `make_manifest.py`, `check_manifest.py` and the files in `data/flows/`.

## 1. Source

- **Dataset:** CIC-IDS2017, Canadian Institute for Cybersecurity, University of
  New Brunswick. Official page: <https://www.unb.ca/cic/datasets/ids-2017.html>
- **File used:** the labelled flow files (`TrafficLabelling`, CSV with IP
  addresses, timestamps and a `Label` column), downloaded from the Hugging Face
  mirror `Mireu-Lab/CIC-IDS`, archive `GeneratedLabelledFlows.zip`.
- **SHA-256 of the archive:** `7bdbef286f8893f31c6db12105fa097fa5c2dcc6733179037a08129d150ea27a`
- **Licence / terms:** see the official page. The raw archive is not committed
  to the repository; only the converted slices and their manifests are.
- **Citation:** Iman Sharafaldin, Arash Habibi Lashkari, Ali A. Ghorbani.
  *Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic
  Characterization.* ICISSP 2018.

## 2. Why this dataset

The simulator was dropped, so traffic comes from prepared datasets only. The
test plan needs real traffic with attack labels to measure detection quality
(DQ tests) and a long benign part for false alarms. CIC-IDS2017 provides both.

## 3. Files in `data/flows/`

| File | Content | Manifest | Episodes |
|------|---------|----------|----------|
| `cic-friday-portscan.csv` | Friday port-scan slice | `.manifest.json` | 8 |
| `cic-tuesday-bruteforce.csv` | Tuesday brute-force slice | `.manifest.json` | 3 |
| `cic-friday-ddos.csv` | Friday DDoS slice | `.manifest.json` | 1 |

Each slice also contains benign flows from the same time range.

## 4. Label mapping

| CIC label | NetGuard `label` |
|-----------|------------------|
| BENIGN | `normal` |
| PortScan | `port_scan` |
| DDoS | `dos` |
| FTP-Patator, SSH-Patator | `brute_force` |

Labels outside the five classes are skipped by default; `--include-other` keeps
them as `suspicious_pattern`. CIC-IDS2017 has **no ground truth for
`abnormal_traffic`**, so that class cannot be measured with this dataset.

## 5. Conversion and time handling

`convert_cic.py` turns the CSV into `flow.v1` rows. Things the dataset requires:

- **Timestamps have minute precision and a 12-hour clock without AM/PM.** An hour
  below 8 is read as afternoon (`--pm-before 8`). `--spread-minutes` spreads the
  flows of one minute over that minute, so a burst is not placed on one second.
- **Flows are bidirectional** in the source; each becomes one flow with the
  initiator as source.
- **Address 172.16.0.1** is the NAT address of the victim network: many attacks
  appear to come from it.
- **Negative durations** are skipped and counted.
- **Direction:** CICFlowMeter names the sender of the first packet "source", so a reply of the victim can be
  recorded server -> client. Attack flows from the victim network (192.168.10.x) to 172.16.0.1 are turned around
  (addresses and ports swapped), so the attacker is always the source, as in the manifests.
- **Label noise:** a few labels in the source are known to be inconsistent;
  they are taken as they are.

## 6. Ground-truth manifests

`make_manifest.py` builds `<file>.manifest.json` (schema `manifest.v1`): flows of
one class from the same attackers are merged into an episode when the gap is
at most 120 s (`gap_s`), with at most 50 attacker hosts (`max_hosts`). The
episodes were compared with the official attack schedule; differences are
written into the `notes` of each manifest.

`check_manifest.py` counts the labelled flows inside each episode and prints
`OK` or `FAILED`, so the manifest and the CSV cannot drift apart.

## 7. Reproduce

```bash
# 1. put the extracted CSV into data/raw/, then convert
python3 services/importer/convert_cic.py data/raw/<file>.csv data/flows/<name>.csv --spread-minutes

# 2. generate and check the manifest
python3 services/importer/make_manifest.py data/flows/<name>.csv
python3 services/importer/check_manifest.py data/flows/<name>.csv   # finds <name>.csv.manifest.json next to it

# 3. import (optional: REPLAY_SPEED=1 for real time)
docker compose --profile import run --rm -e FLOW_FILE=/app/data/flows/<name>.csv importer
docker compose restart processor   # between datasets
```

## 8. Replay and old timestamps (R12)

The data is from 2017. The detection engine uses an event clock per source, so
old timestamps work. The importer can also replay at a set speed
(`REPLAY_SPEED`, `REPLAY_MAX_GAP_S`) and move the timestamps to the present.
Restart the processor between datasets so the per-source clock starts clean.

## 9. Known limitations

- No ground truth for `abnormal_traffic`.
- SSH-Patator times differ from the official schedule by about 10 minutes; the
  cause is not known yet.
- Label noise in the source data affects precision/recall by a small amount.
- The slices are subsets, not the whole days.

## 10. Files for the end-to-end checks (IT-04, IT-09, ST-02, ST-03)

**Small attack files, committed** (`make_scan_fixtures.py`, the same output on every run): one port scan, 300 SYN
packets from 10.0.0.66 to 300 ports of 10.0.0.5 in 8 s, plus a little normal traffic. The default rule fires at 100
ports in 10 s, so the scan is clearly above it.

| File | Used by |
|------|---------|
| `data/flows/scan-small.csv` and `.manifest.json` | ST-02 (flow file with a known attack -> dashboard) |
| `data/pcap/portscan-small.pcap` | ST-03 (PCAP import -> dashboard) |
| `tests/integration/test_e2e_import.py` | IT-09: the same scan with a new attacker address per run, imported through the running stack; the flows are stored and a `port_scan` detection appears |

The time of the files is 2023. For the dashboard import with `REPLAY_SPEED` set, so the flows land in the present
and show up in the charts of the last minutes.

**Real attacks, one slice per class** (IT-04). `slice_flows.py` cuts an episode and the normal traffic around it out
of a dataset file and writes the manifest of the slice:

```bash
python3 services/importer/slice_flows.py data/flows/cic-friday-portscan.csv data/flows/it04-portscan.csv --episode port_scan-003 --pad 30
python3 services/importer/slice_flows.py data/flows/cic-tuesday-bruteforce.csv data/flows/it04-bruteforce.csv --episode brute_force-001 --pad 30 --max-seconds 300
python3 services/importer/slice_flows.py data/flows/cic-friday-ddos.csv data/flows/it04-ddos.csv --episode dos-001 --pad 30 --max-seconds 120
```

For every slice (stack running, **without replay**, so the detections keep the flow time of the manifest):

```bash
make reset && make up
make import FILE=data/flows/it04-portscan.csv
# wait until the processor has caught up (about 30 s), then
python3 tests/quality/evaluate.py data/flows/it04-portscan.csv
```

Expected: the class of the slice is detected for its episode (recall 1.00 for the episode). The result for every class
goes into the test report. The DoS slice is expected to fail until the DoS rule is tuned (test report, DQ-01).

### 10.5 IT-04 results (2026-11-17)

Four slices went through the stack with 0 rejected flows. Precision, recall and F1 come from `tests/quality/evaluate.py`.

| Class | Slice | Result |
|---|---|---|
| port_scan (fast) | `port_scan-005`, first 120 s | found: P 1.00, R 1.00, F1 1.00; 15 detections, 0 false alarms; also reported as `dos` (60 detections) because it exceeds 500 connections/s |
| port_scan (slow) | `port_scan-003` | missed: at most 5 ports in 10 s, the rule needs 100 |
| brute_force | `brute_force-001`, first 300 s | found: F1 1.00; 10 false alarms on normal traffic |
| dos | `dos-001`, first 120 s | missed: peak 180 flows/s and 1,884 packets/s, the rule needs 500 connections/s or 20,000 packets/s; one source (NAT), so the DDoS check (10 or more sources) cannot apply |

The misses come from the detection thresholds, not from the import.

## 11. Import speed on large files (PT-07)

Measured on a MacBook (Darwin arm64, 10 CPUs, Python 3.14) on 2026-11-22 with `tests/performance/import_speed.py`. The test files are generated (a 1,000,000-flow CSV of 74 MB, PCAPs of 150 MB and 60 MB) and are not committed (`data/tmp/`).

Importer alone (read, check, encode; no broker):

| File | Flows | Seconds | Flows/s | Peak memory |
|---|---|---|---|---|
| CSV, 74 MB, schema check only (before) | 1,000,000 | 83.1 | 12,037 | 38 MB |
| CSV, 74 MB, fast check (now) | 1,000,000 | 15.6 | 64,180 | 38 MB |
| PCAP, 150 MB, 10 packets per flow | 209,466 | 23.0 | 9,126 | 274 MB |
| PCAP, 60 MB, 1 packet per flow (worst case) | 837,012 | 18.7 | 44,665 | 934 MB |

Into the running stack (`make import`, 1,000,000 flows, timed from the importer's own log lines):

| Processor and persister | Seconds | Flows/s |
|---|---|---|
| running | 92.8 | 10,780 |
| stopped | 85.5 | 11,692 |

What we found:

- The JSON schema check took most of the time. The importer now runs a fast check in plain Python and asks the schema only when it is not sure, so the rejection reasons are the same. The CSV import is 5.3 times faster (UT-26 compares the two checks).
- A CSV needs the same memory (38 MB) for any size, because it is read in a stream.
- A PCAP is read completely into memory. The memory depends on the number of flows, about 1.1 KB per flow, not on the file size: 934 MB for 837,012 one-packet flows. So the limit of 200 MB (`MAX_PCAP_MB`) stays. A 200 MB capture of one-packet flows could need about 3 GB. Bigger captures are converted to a flow CSV first.
- Reading a PCAP is the slow part: 20.3 s of the 23.0 s for the 150 MB capture, about 105,000 packets per second.
- Into the stack the import reaches about 10,800 flows/s, above the 5,000 flows/s of NFR01. The consumers are not the limit (stopped: 11,692 flows/s). The limit is between the importer and the broker (producer settings with acks=all and idempotence, or the single-core broker). We did not look further because the target is met.
