# Backend Integration

## 1. Provided Interfaces (Backend → Frontend)

The backend exposes a REST API for accessing and managing network monitoring data stored in PostgreSQL.

All endpoints use the `/api` prefix and exchange data in JSON format.

### 1.1 Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | Authenticate a user and issue access and refresh tokens. |
| POST | `/api/auth/refresh` | Obtain a new access token using a valid refresh token. |
| POST | `/api/auth/logout` | Invalidate the current refresh token/session. |
| GET | `/api/auth/me` | Retrieve information about the currently authenticated user. |

### 1.2 Dashboard

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/dashboard/summary` | Retrieve aggregated statistics, including the number of network flows, detections, and alerts within a selected time range. |

### 1.3 Alerts

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/alerts` | Retrieve a paginated list of alerts with filtering and sorting. |
| GET | `/api/alerts/{id}` | Retrieve detailed information about an alert and its related detection. |
| PATCH | `/api/alerts/{id}/acknowledge` | Mark an alert as acknowledged. |

### 1.4 Detections

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/detections` | Retrieve a paginated list of detected anomalies. |
| GET | `/api/detections/{id}` | Retrieve detection details, including type, method, confidence, and explanation. |
| GET | `/api/detections/{id}/flows` | Retrieve network flows associated with a detection. |

### 1.5 Network Flows

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/flows` | Retrieve a paginated list of network flows with filtering and sorting. |
| GET | `/api/flows/{flowId}?tsStart={timestamp}` | Retrieve detailed information about a specific network flow. |

### 1.6 Detection Configuration

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/detection-configurations` | Retrieve available detection configurations. |
| GET | `/api/detection-configurations/{id}` | Retrieve details of a specific detection configuration. |
| POST | `/api/detection-configurations` | Create a new detection configuration. |
| PATCH | `/api/detection-configurations/{id}` | Update an existing detection configuration. |
| PUT | `/api/detection-configurations/{id}/activate` | Set a detection configuration as active. |

### 1.7 Common API Requirements

- **Data format:** JSON over HTTP.
- **Authentication:** Token-based authentication.
- **Authorization:** Protected endpoints require authentication; configuration modifications are restricted to authorized users.
- **Filtering:** Support filtering by time range, severity, detection type, IP address, protocol, and alert status where applicable.
- **Pagination:** List endpoints must support pagination.
- **Sorting:** Support timestamp-based sorting.
- **Error handling:** Standard HTTP status codes and consistent error responses.
- **Documentation:** API contracts will be documented using OpenAPI.
