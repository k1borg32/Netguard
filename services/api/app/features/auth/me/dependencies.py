from app.features.common.dependencies import Database

from .handler import GetCurrentUserHandler


def get_current_user_handler(session: Database) -> GetCurrentUserHandler:
    return GetCurrentUserHandler(session)
