from dataclasses import dataclass, field

from app.infrastructure.security.models import VerifiedRefreshToken


@dataclass(frozen=True)
class LogoutCommand:
    token: VerifiedRefreshToken = field(repr=False)
