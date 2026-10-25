from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BootstrapIn(BaseModel):
    intent: Literal["candidate", "recruiter", "company"]
    company_name: str | None = None
    full_name: str = ""


class MembershipOut(BaseModel):
    company_id: UUID
    role: str


class MeOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str | None
    status: str
    memberships: list[MembershipOut]


class AddMemberIn(BaseModel):
    email: str = Field(min_length=3)
    company_id: UUID | None = None


class MemberOut(BaseModel):
    user_id: UUID
    email: str
    role: str
    company_id: UUID
