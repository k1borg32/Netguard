from app.features.common.app_exception import AppException


class AuthenticationFailed(AppException):
    def __init__(self) -> None:
        super().__init__(401, "Authentication failed")


class UserAlreadyExistsError(AppException):
    def __init__(self) -> None:
        super().__init__(409, "Username already exists")


class ForbiddenError(AppException):
    """Exception raised when a user does not have the required role."""

    def __init__(self) -> None:
        super().__init__(403, "Forbidden")


__all__ = ["AuthenticationFailed", "ForbiddenError", "UserAlreadyExistsError"]
