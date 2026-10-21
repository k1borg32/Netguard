
-- NetGuard - Development Bootstrap
-- Sample data for local development and testing.
-- Run schema.sql before this script.
-- DO NOT execute against production databases.

BEGIN;

-- =========================
-- Detection Configurations
-- =========================

INSERT INTO detection_configs (
    configuration_id,
    detection_type,
    method,
    parameters,
    active
)
VALUES (
    '10000000-0000-0000-0000-000000000001',
    'port_scan',
    'rule',
    '{
        "window_s": 10,
        "unique_dst_ports_threshold": 3
    }'::JSONB,
    TRUE
)
ON CONFLICT DO NOTHING;

-- =========================
-- Network Flows
-- =========================

INSERT INTO network_flows (
    flow_id,
    ts_start,
    trace_id,
    ingested_at,
    duration_ms,
    src_ip,
    dst_ip,
    src_port,
    dst_port,
    protocol,
    packets,
    bytes,
    tcp_flags,
    source
)
VALUES
(
    '20000000-0000-0000-0000-000000000001',
    '2026-10-17 12:00:01+00',
    'trace-001',
    '2026-10-17 12:00:02+00',
    50,
    '192.168.1.10',
    '192.168.1.20',
    52001,
    21,
    'TCP',
    4,
    320,
    'SYN',
    'simulator'
),
(
    '20000000-0000-0000-0000-000000000002',
    '2026-10-17 12:00:02+00',
    'trace-002',
    '2026-10-17 12:00:03+00',
    45,
    '192.168.1.10',
    '192.168.1.20',
    52002,
    22,
    'TCP',
    4,
    300,
    'SYN',
    'simulator'
),
(
    '20000000-0000-0000-0000-000000000003',
    '2026-10-17 12:00:03+00',
    'trace-003',
    '2026-10-17 12:00:04+00',
    55,
    '192.168.1.10',
    '192.168.1.20',
    52003,
    23,
    'TCP',
    5,
    410,
    'SYN',
    'simulator'
),
(
    '20000000-0000-0000-0000-000000000004',
    '2026-10-17 12:00:04+00',
    'trace-004',
    '2026-10-17 12:00:05+00',
    250,
    '192.168.1.30',
    '192.168.1.40',
    53000,
    443,
    'TCP',
    12,
    8400,
    'ACK',
    'simulator'
)
ON CONFLICT DO NOTHING;

-- =========================
-- Detections
-- =========================

INSERT INTO detections (
    detection_id,
    configuration_id,
    created_at,
    first_ingested_at,
    type,
    method,
    severity,
    confidence,
    src_ip,
    dst_ip,
    window_size_s,
    window_start,
    window_end,
    explanation,
    features,
    trace_ids
)
VALUES (
    '30000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    '2026-10-17 12:00:11+00',
    '2026-10-17 12:00:02+00',
    'port_scan',
    'rule',
    'HIGH',
    0.95,
    '192.168.1.10',
    '192.168.1.20',
    10,
    '2026-10-17 12:00:00+00',
    '2026-10-17 12:00:10+00',
    'Source contacted 3 different destination ports within 10 seconds.',
    '{
        "unique_dst_ports": 3,
        "threshold": 3,
        "flow_count": 3
    }'::JSONB,
    ARRAY['trace-001', 'trace-002', 'trace-003']
)
ON CONFLICT DO NOTHING;

-- =========================
-- Alerts
-- =========================

INSERT INTO alerts (
    alert_id,
    detection_id,
    status,
    created_at,
    acknowledged_at
)
VALUES (
    '40000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001',
    'NEW',
    '2026-10-17 12:00:11+00',
    NULL
)
ON CONFLICT DO NOTHING;

COMMIT;

-- =========================
-- Verification
-- =========================

SELECT 'network_flows' AS entity, COUNT(*) FROM network_flows
UNION ALL
SELECT 'detections', COUNT(*) FROM detections
UNION ALL
SELECT 'alerts', COUNT(*) FROM alerts
UNION ALL
SELECT 'detection_configs', COUNT(*) FROM detection_configs;
