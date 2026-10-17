"""Offline checks of the domain's PostgreSQL mappings."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from app.domain import Alert, Base, Detection, DetectionConfig, NetworkFlow, User
from sqlalchemy import CheckConstraint, inspect
from sqlalchemy.dialects.postgresql import INET, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import configure_mappers


def test_models_register_and_compile_without_database_configuration():
    environment = {key: value for key, value in os.environ.items() if key.upper() != "DATABASE_URL"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import socket\n"
            "def reject_connection(*args, **kwargs):\n"
            "    raise AssertionError('Database connection attempted')\n"
            "socket.socket.connect = reject_connection\n"
            "from app.domain import Base\n"
            "from sqlalchemy.orm import configure_mappers\n"
            "from sqlalchemy.schema import CreateTable\n"
            "from sqlalchemy.dialects.postgresql import dialect\n"
            "configure_mappers()\n"
            "assert set(Base.metadata.tables) == "
            "{'network_flows', 'detections', 'alerts', 'detection_configs', 'users'}\n"
            "for table in Base.metadata.sorted_tables:\n"
            "    assert str(CreateTable(table).compile(dialect=dialect()))\n",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_postgresql_types_and_flow_identity():
    assert list(NetworkFlow.__table__.primary_key.columns.keys()) == ["flow_id", "ts_start"]
    assert isinstance(NetworkFlow.__table__.c.flow_id.type, UUID)
    assert isinstance(NetworkFlow.__table__.c.src_ip.type, INET)
    assert isinstance(Detection.__table__.c.features.type, JSONB)
    assert isinstance(DetectionConfig.__table__.c.parameters.type, JSONB)
    assert "analysis_window" not in Detection.__table__.c
    for name in ("window_size_s", "window_start", "window_end"):
        assert not Detection.__table__.c[name].nullable
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, TIMESTAMP):
                assert column.type.timezone
            assert column.default is None
            assert column.server_default is None


def test_constraints_and_relationship_cardinalities():
    configure_mappers()
    assert next(iter(Detection.__table__.c.configuration_id.foreign_keys)).column is (
        DetectionConfig.__table__.c.configuration_id
    )
    assert next(iter(Alert.__table__.c.detection_id.foreign_keys)).column is Detection.__table__.c.detection_id
    assert Alert.__table__.c.detection_id.unique
    assert not Alert.__table__.c.detection_id.nullable
    assert Alert.__table__.c.acknowledged_at.nullable
    assert not inspect(Detection).relationships.alert.uselist
    assert inspect(DetectionConfig).relationships.detections.uselist
    assert not inspect(User).relationships
    checks = {
        str(constraint.sqltext)
        for constraint in Detection.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "confidence BETWEEN 0 AND 1" in checks
    assert "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')" in checks


def test_relationships_synchronize_without_persistence():
    configuration = DetectionConfig(configuration_id=uuid4())
    detection = Detection(detection_id=uuid4(), configuration=configuration)
    alert = Alert(alert_id=uuid4(), detection=detection)

    assert configuration.detections == [detection]
    assert detection.alert is alert
    assert alert.detection is detection
