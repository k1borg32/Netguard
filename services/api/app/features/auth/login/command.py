from dataclasses import dataclass, field


@dataclass(frozen=True)
class LoginCommand:
    username: str
    password: str = field(repr=False)
