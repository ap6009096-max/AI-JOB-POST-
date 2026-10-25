from typing import Any

from pydantic import BaseModel, Field


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


class CompanyProfileOut(BaseModel):
    id: str
    name: str
    industry: str = ""
    business_domain: str = ""
    description: str = ""
    location: str = ""
    company_size: str = ""
    departments: list[str] = Field(default_factory=list)
    hiring_domains: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    can_edit: bool = False


class CompanyProfilePatch(BaseModel):
    name: str | None = None
    industry: str | None = None
    business_domain: str | None = None
    description: str | None = None
    location: str | None = None
    company_size: str | None = None
    departments: list[str] | None = None
    hiring_domains: list[str] | None = None
    technologies: list[str] | None = None


PROFILE_EXTRA_KEYS = (
    "industry",
    "business_domain",
    "description",
    "location",
    "company_size",
    "departments",
    "hiring_domains",
    "technologies",
)


def profile_from_company(company: Any, *, can_edit: bool) -> CompanyProfileOut:
    extras = company.extras if isinstance(getattr(company, "extras", None), dict) else {}
    return CompanyProfileOut(
        id=str(company.id),
        name=company.name,
        industry=str(extras.get("industry") or ""),
        business_domain=str(extras.get("business_domain") or ""),
        description=str(extras.get("description") or ""),
        location=str(extras.get("location") or ""),
        company_size=str(extras.get("company_size") or ""),
        departments=_string_list(extras.get("departments")),
        hiring_domains=_string_list(extras.get("hiring_domains")),
        technologies=_string_list(extras.get("technologies")),
        can_edit=can_edit,
    )


def extras_patch(body: CompanyProfilePatch) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True, exclude={"name"})
    if "departments" in payload:
        payload["departments"] = _string_list(payload["departments"])
    if "hiring_domains" in payload:
        payload["hiring_domains"] = _string_list(payload["hiring_domains"])
    if "technologies" in payload:
        payload["technologies"] = _string_list(payload["technologies"])
    return payload
