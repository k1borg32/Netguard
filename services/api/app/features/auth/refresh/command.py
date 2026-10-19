from dataclasses import dataclass, field

from app.abstraction.auth.models import VerifiedRefreshToken


@dataclass(frozen=True)
class RefreshCommand:
    token: VerifiedRefreshToken = field(repr=False)
