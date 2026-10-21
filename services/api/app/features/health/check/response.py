from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    status: str
    db: str
