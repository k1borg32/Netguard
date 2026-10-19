from pydantic import BaseModel, ConfigDict, Field

from app.abstraction.auth.enums import UserRole


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=128, pattern=r"^\S+$")
    password: str = Field(min_length=12, max_length=1024, repr=False)
    role: UserRole = UserRole.USER
