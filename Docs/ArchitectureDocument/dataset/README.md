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
| `cic-friday-ddos.csv` | Friday DDoS slice | `.manifest.json` | 2 |

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
