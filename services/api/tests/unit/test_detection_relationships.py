"""Exercise domain relationships in memory, without a database or mocks."""

from app.domain import Alert, Detection, DetectionConfig


def test_assigning_configuration_connects_both_sides() -> None:
    configuration = DetectionConfig()
    detection = Detection(configuration=configuration)

    assert detection.configuration is configuration
    assert configuration.detections == [detection]


def test_moving_detection_removes_it_from_previous_configuration() -> None:
    previous = DetectionConfig()
    current = DetectionConfig()
    detection = Detection(configuration=previous)

    detection.configuration = current

    assert previous.detections == []
    assert current.detections == [detection]
    assert detection.configuration is current


def test_replacing_alert_disconnects_previous_alert() -> None:
    detection = Detection()
    previous = Alert(detection=detection)
    current = Alert()

    detection.alert = current

    assert previous.detection is None
    assert current.detection is detection
    assert detection.alert is current
