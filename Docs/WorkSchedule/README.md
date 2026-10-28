# NetGuard - Work Schedule

Version 1.0, week 3 (2026-10-27). The project runs for ten weeks; week 1 started on 12 October 2026.
Tasks are tracked as GitHub issues with a "Week N" milestone, so this schedule and the issue list show the same plan.

## 1. Team

| Role | Who | Area | Main deliverables |
|---|---|---|---|
| M1 | Valeriia | Network Data & Flow Processing | flow model, PCAP and flow-file importer, labelled dataset and ground truth |
| M2 | Kuzma | Anomaly Detection & Algorithms | time windows, features, rules, statistical method, classification, thresholds |
| M3 | Jakub | Backend & Data Storage | domain model, database, persister, REST API, authentication, alerts |
| M4 | Daniyar | Frontend & Visualization | monitoring dashboard |
| M5 | Vlad | Infrastructure, Testing & DevOps | Docker Compose, CI, test plan and report, integration, performance, resilience and security tests |

## 2. Milestones

| Week | Milestone | State on 2026-10-27 |
|---|---|---|
| 1 | Vision document, test plan, repository, CI and a running skeleton of the pipeline | done |
| 2 | Architecture document (one section per area), detection message contract, test plan v0.3 | done, except the detection engine section (M2) |
| 3 | Data import from PCAP and flow files, API for detections and flows, Vision v1.2 and test plan v0.4 after the simulator was dropped, this schedule | in progress (PR #50, #51) |
| 4 | Mid-term presentation: pipeline running on the labelled dataset, dashboard overview, first performance baseline | planned |
| 5 | Detection engine v1 (windows, rules, statistical method) and the first detection quality results | planned |
| 6 | API complete (filters, configuration, rate limiting), API and security tests | planned |
| 7 | Dashboard complete, end-to-end tests | planned |
| 8 | Performance and resilience campaign | planned |
| 9 | Full regression, final detection quality, security scans, test report | planned |
| 10 | Fixes and re-test, final presentation and demo on a clean clone | planned |

## 3. Plan per week

| Week | M1 Valeriia | M2 Kuzma | M3 Jakub | M4 Daniyar | M5 Vlad |
|---|---|---|---|---|---|
| 1 | flow model and normalisation rules | detection approach: windows, rules, statistical method | Vision v1.0, start of the domain model | dashboard requirements | repository, Compose skeleton, CI, Vision v1.1 with M3, test plan v0.2 |
| 2 | architecture: ingestion and flow model | architecture: detection engine | domain model, database schema, authentication, alerts and summary API | architecture: dashboard, wireframes, React app skeleton | architecture: deployment, CI/CD and testing; detection contract; test plan v0.3 |
| 3 | importer for PCAP and flow files (#51), dataset proposal (#52) | time windows (1/10/60 s) and features in the processor | detections, flows and time-series endpoints (#47, #49) | login and layout done, overview cards | importer tests (#7), Vision v1.2, test plan v0.4, this schedule |
| 4 | labelled dataset: subset, mapping to our classes, ground truth (#52) | rules: port scan, DoS, brute force, suspicious connection pattern | detection configuration endpoints (#48), alerts created from detections | overview with stat cards and trend charts (#34) | performance baseline (#10), clean machine check (#11), mid-term demo |
| 5 | replay of large files, ground truth checks | statistical method (abnormal traffic, unknown), classification, first quality results with M5 | alert details with evidence, history filters | alerts list, alert details, acknowledge (#35) | detection quality evaluation script (#12) |
| 6 | importer robustness (broken and large files) | thresholds configurable at runtime, threshold sweep | rate limiting, persister reconnect (#9) | history and flows screens (#36) | API and security tests (#13) |
| 7 | end-to-end checks of the import | tuning after the error analysis | fixes from the API tests | settings screen (#37) | end-to-end tests with Playwright (#14) |
| 8 | import performance on large files | processor scaling and failover | persistence under load | loading, error and empty states, accessibility (#38) | performance campaign (#15), resilience tests (#16) |
| 9 | test campaign | final detection quality on the common test set | test campaign, fixes | npm audit, screenshots (#39) | security scans (#17), test report (#18) |
| 10 | fixes, final presentation | fixes, final presentation | fixes, final presentation | fixes, final presentation | re-test, demo rehearsal on a clean clone (#19) |

Weeks 9 and 10 are shared: everyone takes part in the test campaign, fixes their own defects and prepares their part
of the final presentation.

## 4. Changes to the plan

- **Week 3:** the supervisors removed the traffic simulator from the requirements. The simulator scenarios planned for
  week 4 and the simulator control in the API and on the dashboard (weeks 6-7) are dropped. Test data now comes from a
  public labelled dataset and small captures (week 4, M1). The simulator code stays only as a load generator for the
  performance tests (M5).
- **Week 2:** the dashboard skeleton was finished one week early, so the overview screen starts in week 3.
