from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.abstraction.auth.enums import UserRole


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    username: str
    role: UserRole
