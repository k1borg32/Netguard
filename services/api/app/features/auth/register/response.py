from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.user_role import UserRole


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    username: str
    role: UserRole
