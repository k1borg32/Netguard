-- Initial schema - SKELETON (owner: Member 3). Runs once on first DB start.
-- Real migrations (Alembic / Django migrations) replace this in week 6.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS flows (
    flow_id      UUID        NOT NULL,
    trace_id     TEXT        NOT NULL,
    ingested_at  TIMESTAMPTZ NOT NULL,
    ts_start     TIMESTAMPTZ NOT NULL,
    duration_ms  DOUBLE PRECISION,
    src_ip       INET        NOT NULL,
    dst_ip       INET        NOT NULL,
    src_port     INTEGER,
    dst_port     INTEGER,
    protocol     TEXT,
    packets      BIGINT,
    bytes        BIGINT,
    tcp_flags    TEXT,
    source       TEXT,
    label        TEXT,
    PRIMARY KEY (flow_id, ts_start)
);
SELECT create_hypertable('flows', 'ts_start', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS flows_src_idx   ON flows (src_ip, ts_start DESC);
CREATE INDEX IF NOT EXISTS flows_trace_idx ON flows (trace_id);

CREATE TABLE IF NOT EXISTS detections (
    detection_id      UUID PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL,
    first_ingested_at TIMESTAMPTZ NOT NULL,
    type              TEXT NOT NULL,
    method            TEXT NOT NULL,
    severity          TEXT NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    confidence        DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    src_ip            INET,
    dst_ip            INET,
    window_size_s     INTEGER NOT NULL,
    window_start      TIMESTAMPTZ NOT NULL,
    window_end        TIMESTAMPTZ NOT NULL,
    features          JSONB NOT NULL,
    explanation       TEXT NOT NULL,
    trace_ids         TEXT[] NOT NULL
);
CREATE INDEX IF NOT EXISTS det_filter_idx ON detections (created_at DESC, type, severity);
CREATE INDEX IF NOT EXISTS det_src_idx    ON detections (src_ip);
CREATE INDEX IF NOT EXISTS det_trace_idx  ON detections USING GIN (trace_ids);

-- Pipeline latency view used by the performance test (NFR02).
CREATE OR REPLACE VIEW detection_latency AS
SELECT detection_id, EXTRACT(EPOCH FROM (created_at - first_ingested_at)) AS latency_s
FROM detections;
