from app.features.common.app_exception import AppException


class DetectionConfigurationNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__(404, "Detection configuration not found")
