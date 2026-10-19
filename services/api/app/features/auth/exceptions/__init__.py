from app.features.common.app_exception import AppException


class AuthenticationFailed(AppException):
    def __init__(self) -> None:
        super().__init__(401, "Authentication failed")


class UserAlreadyExistsError(AppException):
    def __init__(self) -> None:
        super().__init__(409, "Username already exists")


class UserNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__(404, "User not found")


class AuthStorageError(AppException):
    def __init__(self) -> None:
        super().__init__(503, "Authentication storage unavailable")


class ForbiddenError(AppException):
    """Exception raised when a user does not have the required role."""

    def __init__(self):
        super().__init__(403, "Forbidden")


__all__ = ["AuthenticationFailed", "AuthStorageError", "ForbiddenError", "UserAlreadyExistsError", "UserNotFoundError"]
