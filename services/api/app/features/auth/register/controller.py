from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.domain.user_role import UserRole
from app.features.auth.common.authentication import require_roles

from .command import RegisterCommand
from .dependencies import get_register_handler
from .handler import RegisterHandler
from .request import RegisterRequest
from .response import RegisterResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def register(
    request: RegisterRequest,
    handler: Annotated[RegisterHandler, Depends(get_register_handler)],
) -> RegisterResponse:
    return await handler.handle(RegisterCommand(request.username, request.password, request.role))
