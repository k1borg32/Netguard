from dataclasses import dataclass


@dataclass(frozen=True)
class ListConfigurationsQuery:
    detection_type: str | None
    method: str | None
    active: bool | None
    sort_order: str
    page: int
    page_size: int
