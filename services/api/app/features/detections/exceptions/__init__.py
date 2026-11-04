from app.features.common.app_exception import AppException


class DetectionNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__(404, "Detection not found")
