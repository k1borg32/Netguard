from uuid import UUID

from pydantic import BaseModel

from app.domain.user_role import UserRole


class CurrentUserResponse(BaseModel):
    user_id: UUID
    username: str
    role: UserRole
