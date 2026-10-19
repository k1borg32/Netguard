from dataclasses import dataclass, field

from app.infrastructure.security.models import VerifiedRefreshToken


@dataclass(frozen=True)
class RefreshCommand:
    token: VerifiedRefreshToken = field(repr=False)
