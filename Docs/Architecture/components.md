
# NetGuard – Component Architecture

The system consists of independent components communicating through a message broker, shared Dtabase storage, and REST API.

![NetGuard_Component_Diagram](./diagrams/component_diagram.svg)

## Components

- **PCAP Importer** – Reads captured network traffic and publishes packet events to the message broker.
- **Traffic Simulator** – Generates synthetic network traffic and publishes packet events to the message broker.
- **Message Broker** – Delivers packet events to the Flow Processor.
- **Flow Processor** – Converts packets into network flows, forwards them to the Detection Engine, and persists them in TimescaleDB.
- **Detection Engine** – Analyzes network flows, detects anomalies, and persists detections and alerts directly in TimescaleDB. Reads its configuration from the database.
- **Database** – Stores flows, detections, alerts, configurations, and user data.
- **Monitoring Dashboard** – Allows operators to monitor network activity, inspect alerts, and manage detection settings through the REST API.

