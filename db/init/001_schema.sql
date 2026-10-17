
-- NetGuard - TimescaleDB Bootstrap
-- Initial database schema

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =========================
-- Users
-- =========================

CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
);

-- =========================
-- Detection Configurations
-- =========================

CREATE TABLE detection_configs (
    configuration_id UUID PRIMARY KEY,
    detection_type TEXT NOT NULL,
    method TEXT NOT NULL,
    parameters JSONB NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE
);

-- =========================
-- Network Flows
-- =========================

CREATE TABLE network_flows (
    flow_id UUID NOT NULL,
    ts_start TIMESTAMPTZ NOT NULL,
    trace_id TEXT,
    ingested_at TIMESTAMPTZ,
    duration_ms DOUBLE PRECISION,
    src_ip INET,
    dst_ip INET,
    src_port INTEGER,
    dst_port INTEGER,
    protocol TEXT,
    packets BIGINT,
    bytes BIGINT,
    tcp_flags TEXT,
    source TEXT,

    PRIMARY KEY (flow_id, ts_start)
);

SELECT create_hypertable(
    'network_flows',
    'ts_start',
    if_not_exists => TRUE
);

CREATE INDEX network_flows_src_idx
    ON network_flows (src_ip, ts_start DESC);

CREATE INDEX network_flows_dst_idx
    ON network_flows (dst_ip, ts_start DESC);

CREATE INDEX network_flows_trace_idx
    ON network_flows (trace_id);

-- =========================
-- Detections
-- =========================

CREATE TABLE detections (
    detection_id UUID PRIMARY KEY,
    configuration_id UUID REFERENCES detection_configs(configuration_id),
    created_at TIMESTAMPTZ NOT NULL,
    first_ingested_at TIMESTAMPTZ,
    type TEXT NOT NULL,
    method TEXT NOT NULL,
    severity TEXT NOT NULL
        CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    confidence DOUBLE PRECISION
        CHECK (confidence BETWEEN 0 AND 1),
    src_ip INET,
    dst_ip INET,
    src_port INTEGER,
    dst_port INTEGER,
    protocol TEXT,
    window_size_s INTEGER,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    explanation TEXT,
    features JSONB,
    trace_ids TEXT[] NOT NULL DEFAULT '{}'::TEXT[]
);

CREATE INDEX detections_created_idx
    ON detections (created_at DESC);

CREATE INDEX detections_type_severity_idx
    ON detections (type, severity);

CREATE INDEX detections_src_idx
    ON detections (src_ip);

CREATE INDEX detections_trace_idx
    ON detections USING GIN (trace_ids);

-- =========================
-- Alerts
-- =========================

CREATE TABLE alerts (
    alert_id UUID PRIMARY KEY,
    detection_id UUID NOT NULL UNIQUE
        REFERENCES detections(detection_id),
    status TEXT NOT NULL DEFAULT 'NEW',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ
);

CREATE INDEX alerts_created_idx
    ON alerts (created_at DESC);

CREATE INDEX alerts_status_idx
    ON alerts (status, created_at DESC);

-- =========================
-- Detection Latency View
-- =========================

CREATE VIEW detection_latency AS
SELECT
    detection_id,
    EXTRACT(
        EPOCH FROM (created_at - first_ingested_at)
    ) AS latency_s
FROM detections;
