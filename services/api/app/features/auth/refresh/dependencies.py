from app.features.auth.common.dependencies import Tokens
from app.features.common.dependencies import Database

from .handler import RefreshHandler


def get_refresh_handler(session: Database, tokens: Tokens) -> RefreshHandler:
    return RefreshHandler(session, tokens)
