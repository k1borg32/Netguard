from app.features.common.dependencies import Database

from .handler import LogoutHandler


def get_logout_handler(session: Database) -> LogoutHandler:
    return LogoutHandler(session)
