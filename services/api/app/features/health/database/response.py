from typing import Literal

from pydantic import BaseModel


class DatabaseHealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "unavailable"]
