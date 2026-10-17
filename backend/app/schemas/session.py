from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models import Role
from app.schemas.common import ApiDatetime


class SessionUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    role: Role
    on_duty: bool


class SessionIn(BaseModel):
    user_id: UUID


class SessionOut(BaseModel):
    token: str
    expires_at: ApiDatetime
    user: SessionUserOut
    community_id: UUID
