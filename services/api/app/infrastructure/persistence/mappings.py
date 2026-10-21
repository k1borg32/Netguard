"""Attach ORM mappings to pure domain classes at composition time."""

from sqlalchemy.orm import registry, relationship

from app.domain import Alert, Detection, DetectionConfig, NetworkFlow, RefreshSession, User

from .tables import alerts, auth_refresh_sessions, detection_configs, detections, metadata, network_flows, users

mapper_registry = registry(metadata=metadata)


def configure_mappings() -> None:
    if User in {mapper.class_ for mapper in mapper_registry.mappers}:
        return
    mapper_registry.map_imperatively(User, users)
    mapper_registry.map_imperatively(RefreshSession, auth_refresh_sessions)
    mapper_registry.map_imperatively(NetworkFlow, network_flows)
    mapper_registry.map_imperatively(
        DetectionConfig,
        detection_configs,
        properties={"detections": relationship(Detection, back_populates="configuration", lazy="raise")},
    )
    mapper_registry.map_imperatively(
        Detection,
        detections,
        properties={
            "configuration": relationship(DetectionConfig, back_populates="detections", lazy="raise"),
            "alert": relationship(Alert, back_populates="detection", uselist=False, lazy="raise"),
        },
    )
    mapper_registry.map_imperatively(
        Alert,
        alerts,
        properties={"detection": relationship(Detection, back_populates="alert", lazy="raise")},
    )
