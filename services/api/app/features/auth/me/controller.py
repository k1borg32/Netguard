from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.features.auth.common.authentication import get_authenticated_user_id

from .dependencies import get_current_user_handler
from .handler import GetCurrentUserHandler
from .query import GetCurrentUserQuery
from .response import CurrentUserResponse

router = APIRouter()


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    user_id: Annotated[UUID, Depends(get_authenticated_user_id)],
    handler: Annotated[GetCurrentUserHandler, Depends(get_current_user_handler)],
) -> CurrentUserResponse:
    return await handler.handle(GetCurrentUserQuery(user_id))
