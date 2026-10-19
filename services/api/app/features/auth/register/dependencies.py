from app.features.auth.common.dependencies import Hasher
from app.features.common.dependencies import Database

from .handler import RegisterHandler


def get_register_handler(session: Database, hasher: Hasher) -> RegisterHandler:
    return RegisterHandler(session, hasher)
