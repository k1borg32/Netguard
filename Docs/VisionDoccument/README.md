# NetGuard - Vision Document v1.1

## 1. Introduction and Document Purpose

NetGuard is a network traffic analysis platform designed to detect, classify, and report anomalous network behavior.

This document defines the project scope, system requirements, use cases, constraints, and validation criteria.
Version 1.1 aligns the requirements with the project specification; the changes are listed in section 10.

## 2. Problem and Context

Network traffic generates large volumes of events that cannot be efficiently analyzed manually. Suspicious activity often requires analysis of multiple connections within defined time windows.

The system addresses the detection of:

- Port scanning
- DoS/DDoS-like traffic
- Brute-force patterns
- Abnormal traffic rates
- Suspicious connection patterns
- Anomalies that do not match any known pattern (Unknown Anomaly)

Problem-context diagram
![Netguard problem - context diagram](./diagrams/problem_diagram.svg)

## 3. System Goal and Expected Benefits

**Goal:** Implement a system for automated network traffic anomaly detection using rule-based and statistical or machine learning methods.

**Expected results:**

- Automated processing of network traffic data.
- Detection and classification of anomalies.
- Generation of alerts with supporting evidence.
- Historical data storage and retrieval.
- Visualization of network activity and detection results.
- Measurement of detection accuracy and processing performance.

## 4. Users and Stakeholders

| Role | Responsibility |
|---|---|
| End User | Monitors network traffic, views detected anomalies, and analyzes alerts. With the administrator role, also configures detection thresholds. |
| Project Supervisor | Oversees the development team and monitors project progress. |
| Development Team | Designs, implements, tests, and delivers the system. |

## 5. Use Cases

| ID | Use Case | Role |
|---|---|---|
| UC-01 | Import PCAP files | End User |
| UC-02 | View detected anomalies and alerts | End User |
| UC-03 | View detection evidence and details | End User |
| UC-04 | Browse historical detections | End User |
| UC-05 | Filter alerts by type, severity and time | End User |
| UC-06 | View network traffic statistics | End User |
| UC-07 | Configure detection thresholds | End User (administrator) |
| UC-08 | View network flow details | End User |
| UC-09 | Acknowledge an alert | End User |
| UC-10 | Generate synthetic network traffic | Developer |
| UC-11 | Configure traffic simulation parameters | Developer |
| UC-12 | Start traffic simulation | Developer |
| UC-13 | Stop traffic simulation | Developer |


## 6. Product Function Overview

**Processing pipeline:**

`PCAP / Simulator → Flow Processing → Detection Engine → Storage / API → Dashboard`
![Netguard sequence diagram](./diagrams/network_processing_sequence_diagram.svg)

**Core components:**

- PCAP Importer
- Traffic Simulator
- Flow Processor
- Detection Engine
- Alert Management
- Database
- REST API
- Monitoring Dashboard

![Netguard component diagram](./diagrams/netguard_component_diagram.svg)

## 7. Requirements

### 7.1 Functional Requirements

| ID | Area | Requirement |
|---|---|---|
| F01 | Data ingestion | Import prepared PCAP/flow data, validate input, and report rejected records with the reason. |
| F02 | Flow extraction | Convert traffic into a normalised flow model. |
| F03 | Feature extraction | Calculate temporal, volume, and connection-related features. |
| F04 | Stream processing | Process data continuously using inter-component communication. |
| F05 | Time windows | Analyse using at least 1 s, 10 s, and 60 s windows. |
| F06 | Rule-based detection | Detect Port Scan, DoS/DDoS-like Traffic, Brute Force, and Suspicious Connection Pattern using rules and thresholds evaluated in time windows. |
| F07 | Second detection method | Implement a statistical or ML-based method, e.g. z-score, moving statistics, Isolation Forest, or equivalent. It detects Abnormal Traffic (significant deviation from the historical traffic level) and anomalies that match no known class. |
| F08 | Classification | Classify each detection as Port Scan, DoS/DDoS-like Traffic, Brute Force, Abnormal Traffic, Suspicious Connection Pattern, or Unknown Anomaly, and store type, severity, confidence, timestamp, source, destination, and detection ID. |
| F09 | Explainability | Provide evidence and feature values explaining the alert. |
| F10 | Database | Persist flows, detections, configuration, and historical data. |
| F11 | REST API | Expose flows, current data, history, statistics, alerts, system metrics, and configuration and control of the traffic simulator. |
| F12 | Dashboard | Provide traffic monitoring, alerts, statistics, trend charts, and detection details. |
| F13 | Filtering | Filter history by at least time, type, severity, and source. |
| F14 | Simulator | Generate normal traffic and the five anomalous scenarios from section 2, with a configurable number of hosts, event rate, share of anomalous traffic, and load profiles. |
| F15 | Traceability | Allow an event to be traced from input to the generated detection. |
| F16 | Detection configuration | Thresholds and parameters of the detection methods are configurable; changing them at runtime is an administrative operation. |
| F17 | Alert management | Generate alerts from detections and allow the operator to acknowledge an alert; the alert status is stored. |

### 7.2 Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR01 | Performance | Process at least 5,000 flows/s for a minimum of 5 minutes. Throughput is also measured at other load levels (100, 1,000, 10,000 flows/s and higher, up to 50,000 flows/s or the saturation point). |
| NFR02 | Latency | At 5,000 flows/s, p95 detection latency must not exceed 3 s in the nominal failure-free scenario. Latency is measured from the moment the data needed for the detection is in the system (ingestion of the last flow that contributed to it) to the creation of the detection. |
| NFR03 | Scalability | At least one processing component must support more than one instance. |
| NFR04 | Resilience | Restart/failure of one processing instance must not stop the entire platform. |
| NFR05 | Reproducibility | The complete system must be deployable using one documented procedure. |
| NFR06 | Security | The API must provide authentication, authorisation for administrative operations, input validation, and basic API-abuse protection. |
| NFR07 | Testability | Key components must have unit and integration tests. |
| NFR08 | Observability | Logs must support tracing data flow and diagnosing failures. |
| NFR09 | Data | No dependency on production data or real networks. |
| NFR10 | Documentation | The repository must contain deployment, configuration, testing, and demonstration instructions. |
| NFR11 | Detection quality | Precision, recall, and F1 are measured per anomaly class on a common labelled test set. Initial targets, reviewed after the first measurement in week 5: precision and recall of at least 0.90 for the rule-based classes, macro F1 of at least 0.80, and no HIGH/CRITICAL false alarms on normal traffic. |

## 8. Assumptions, Constraints and Dependencies

**Assumptions:**

- Input consists of prepared PCAP datasets and synthetic traffic.
- Detection methods operate on network flow features.
- Test datasets contain identifiable normal and anomalous traffic.

**Constraints:**

- Five-person development team.
- Ten-week development period.
- No unauthorized monitoring of external networks.
- No development of real-world attack tools.
- Commercial SIEM/IDS functionality is out of scope.

**Dependencies:**

- Availability of suitable network traffic datasets.
- Defined network flow and detection result contracts.
- Integration between processing, detection, storage, and visualization components.

## 9. Test Data and Demonstration Environment

**Test data:**

- Normal network traffic.
- Port scanning scenarios.
- DoS/DDoS-like traffic.
- Brute-force patterns.
- Abnormal traffic rates.
- Suspicious connection patterns.
- Synthetic load-testing datasets.

**Demonstration:**

- Import a prepared PCAP file or start traffic simulation.
- Process network flows and execute anomaly detection.
- Store generated alerts.
- Display alerts, evidence, and traffic statistics.
- Present detection quality and performance measurements.

**Environment:** Reproducible, isolated deployment using documented configuration.

## 10. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-10-12 | Jakub | Initial version. |
| 1.1 | 2026-10-14 | Vlad, agreed with Jakub | Requirements aligned with the project specification: six anomaly classes (F06-F08), input error reporting (F01), API for metrics and simulator control (F11), trend charts (F12), five simulator scenarios and simulator parameters (F14), detection configuration (F16), alert management (F17), throughput load levels (NFR01), latency definition (NFR02), detection quality (NFR11). |
