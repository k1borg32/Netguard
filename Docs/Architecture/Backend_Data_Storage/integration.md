# Backend Integration

## 1. Provided Interfaces (Backend -> Frontend)

The backend exposes a REST API for accessing and managing network monitoring data stored in TimescaleDB.

All endpoints use the `/api/v1/v1` prefix and exchange data in JSON format.

### 1.1 Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Authenticate a user and issue access and refresh tokens. |
| POST | `/api/v1/auth/refresh` | Obtain a new access token using a valid refresh token. |
| POST | `/api/v1/auth/logout` | Invalidate the current refresh token/session. |
| GET | `/api/v1/auth/me` | Retrieve information about the currently authenticated user. |

### 1.2 Dashboard

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/dashboard/summary` | Retrieve aggregated statistics, including the number of network flows, detections, and alerts within a selected time range. |

### 1.3 Alerts

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/alerts` | Retrieve a paginated list of alerts with filtering and sorting. |
| GET | `/api/v1/alerts/{id}` | Retrieve detailed information about an alert and its related detection. |
| PATCH | `/api/v1/alerts/{id}/acknowledge` | Mark an alert as acknowledged. |

### 1.4 Detections

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/detections` | Retrieve a paginated list of detected anomalies. |
| GET | `/api/v1/detections/{id}` | Retrieve detection details, including type, method, confidence, and explanation. |
| GET | `/api/v1/detections/{id}/flows` | Retrieve network flows associated with a detection. |

### 1.5 Network Flows

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/flows` | Retrieve a paginated list of network flows with filtering and sorting. |
| GET | `/api/v1/flows/{flowId}?tsStart={timestamp}` | Retrieve detailed information about a specific network flow. |

### 1.6 Detection Configuration

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/detection-configurations` | Retrieve available detection configurations. |
| GET | `/api/v1/detection-configurations/{id}` | Retrieve details of a specific detection configuration. |
| POST | `/api/v1/detection-configurations` | Create a new detection configuration. |
| PATCH | `/api/v1/detection-configurations/{id}` | Update an existing detection configuration. |
| PUT | `/api/v1/detection-configurations/{id}/activate` | Set a detection configuration as active. |

### 1.7 Common API Requirements

- **Data format:** JSON over HTTP.
- **Authentication:** Token-based authentication.
- **Authorization:** Protected endpoints require authentication; configuration modifications are restricted to authorized users.
- **Filtering:** Support filtering by time range, severity, detection type, IP address, protocol, and alert status where applicable.
- **Pagination:** List endpoints must support pagination.
- **Sorting:** Support timestamp-based sorting.
- **Error handling:** Standard HTTP status codes and consistent error responses.
- **Documentation:** API contracts will be documented using OpenAPI.

## 2. Required Interfaces (Backend -> Database)

The backend requires direct access to TimescaleDB. It does not communicate directly with the Flow Processor or Detection Engine.

### 2.1 Database Access

| Data | Required Operations |
|---|---|
| Network Flows | Read, filter, paginate |
| Detections | Read, filter, paginate |
| Alerts | Read, update status |
| Detection Configurations | Read, create, update, activate |
| Users / Sessions | Authenticate users, manage sessions |
| Statistics | Execute aggregation queries |

### 2.2 Data Dependencies

The backend relies on data persisted by other components:

- **Flow Processor** - Writes network flows directly to TimescaleDB.
- **Detection Engine** - Writes detections and alerts directly to TimescaleDB and reads active detection configurations.
- **Backend Application** - Reads monitoring data and updates information managed by the operator.

All components must follow the agreed database schema and data types.

## 3. Integration Flow

### 3.1 Traffic Processing

1. PCAP Importer or Traffic Simulator publishes packet events to the Message Broker.
2. Flow Processor consumes packet events, generates network flows, and stores them in TimescaleDB.
3. Detection Engine analyzes flows and stores detections and alerts directly in TimescaleDB.

### 3.2 Monitoring

1. Frontend sends HTTP requests to the Backend API.
2. Backend retrieves the requested data from TimescaleDB.
3. Backend returns JSON responses to the frontend.

### 3.3 Configuration Management

1. Operator modifies detection settings through the frontend.
2. Backend validates and stores the configuration in TimescaleDB.
3. Detection Engine reads the active configuration directly from TimescaleDB.

## 4. Integration Constraints

- The backend must remain independent of traffic processing and anomaly detection.
- Backend unavailability must not interrupt flow processing or detection persistence.
- Components must use a consistent database schema.
- Detection-to-flow correlation must be supported by an agreed data contract.
- Only authorized users can modify alerts and detection configurations.
- Real-time updates and advanced analytics are outside the initial MVP scope.