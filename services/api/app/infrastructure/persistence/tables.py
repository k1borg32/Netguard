"""Mappings of the existing PostgreSQL schema, without runtime migrations."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Double,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, TIMESTAMP, UUID

from app.domain.user_role import UserRole

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("user_id", UUID(as_uuid=True), primary_key=True),
    Column("username", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column(
        "role",
        Enum(UserRole, native_enum=False, values_callable=lambda roles: [role.value for role in roles]),
        nullable=False,
    ),
)

auth_refresh_sessions = Table(
    "auth_refresh_sessions",
    metadata,
    Column("token_hash", Text, primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'"),
)

detection_configs = Table(
    "detection_configs",
    metadata,
    Column("configuration_id", UUID(as_uuid=True), primary_key=True),
    Column("detection_type", Text, nullable=False),
    Column("method", Text, nullable=False),
    Column("parameters", JSONB, nullable=False),
    Column("active", Boolean, nullable=False, server_default=text("false")),
)

network_flows = Table(
    "network_flows",
    metadata,
    Column("flow_id", UUID(as_uuid=True), primary_key=True),
    Column("ts_start", TIMESTAMP(timezone=True), primary_key=True),
    Column("trace_id", Text),
    Column("ingested_at", TIMESTAMP(timezone=True)),
    Column("duration_ms", Double),
    Column("src_ip", INET),
    Column("dst_ip", INET),
    Column("src_port", Integer),
    Column("dst_port", Integer),
    Column("protocol", Text),
    Column("packets", BigInteger),
    Column("bytes", BigInteger),
    Column("tcp_flags", Text),
    Column("source", Text),
    Column("label", Text),
)

detections = Table(
    "detections",
    metadata,
    Column("detection_id", UUID(as_uuid=True), primary_key=True),
    Column("configuration_id", UUID(as_uuid=True), ForeignKey("detection_configs.configuration_id")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("first_ingested_at", TIMESTAMP(timezone=True)),
    Column("last_ingested_at", TIMESTAMP(timezone=True)),
    Column("type", Text, nullable=False),
    Column("method", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("confidence", Double),
    Column("src_ip", INET),
    Column("dst_ip", INET),
    Column("src_port", Integer),
    Column("dst_port", Integer),
    Column("protocol", Text),
    Column("window_size_s", Integer),
    Column("window_start", TIMESTAMP(timezone=True)),
    Column("window_end", TIMESTAMP(timezone=True)),
    Column("explanation", Text),
    Column("features", JSONB),
    Column("trace_ids", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")),
    CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="detections_severity_check"),
    CheckConstraint("confidence BETWEEN 0 AND 1", name="detections_confidence_check"),
)

alerts = Table(
    "alerts",
    metadata,
    Column("alert_id", UUID(as_uuid=True), primary_key=True),
    Column("detection_id", UUID(as_uuid=True), ForeignKey("detections.detection_id"), nullable=False, unique=True),
    Column("status", Text, nullable=False, server_default=text("'NEW'")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Column("acknowledged_at", TIMESTAMP(timezone=True)),
)
