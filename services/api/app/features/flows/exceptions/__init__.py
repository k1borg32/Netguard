from app.features.common.app_exception import AppException


class FlowNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__(404, "Flow not found")
