"""Exercise mapped domain relationships in memory, without a database or mocks."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.domain import Alert, Detection, DetectionConfig
from app.infrastructure.persistence.mappings import configure_mappings


@pytest.fixture(autouse=True)
def mappings() -> None:
    configure_mappings()


def configuration() -> DetectionConfig:
    return DetectionConfig(configuration_id=uuid4(), detection_type="port_scan", method="threshold", parameters={})


def new_detection() -> Detection:
    return Detection(
        detection_id=uuid4(), created_at=datetime.now(UTC), type="port_scan", method="threshold", severity="HIGH"
    )


def new_alert(detection: Detection) -> Alert:
    return Alert(alert_id=uuid4(), detection_id=detection.detection_id, status="NEW", created_at=datetime.now(UTC))


def test_assigning_configuration_connects_both_sides() -> None:
    config = configuration()
    detection = new_detection()
    detection.configuration = config

    assert detection.configuration is config
    assert config.detections == [detection]


def test_moving_detection_removes_it_from_previous_configuration() -> None:
    previous = configuration()
    current = configuration()
    detection = new_detection()
    detection.configuration = previous

    detection.configuration = current

    assert previous.detections == []
    assert current.detections == [detection]
    assert detection.configuration is current


def test_replacing_alert_disconnects_previous_alert() -> None:
    detection = new_detection()
    previous = new_alert(detection)
    previous.detection = detection
    current = new_alert(detection)

    detection.alert = current

    assert previous.detection is None
    assert current.detection is detection
    assert detection.alert is current
