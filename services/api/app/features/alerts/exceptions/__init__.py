from app.features.common.app_exception import AppException


class AlertNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__(404, "Alert not found")
