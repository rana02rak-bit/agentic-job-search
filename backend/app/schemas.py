from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class PriorityValue(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SourceValue(StrEnum):
    USER = "USER"
    AI = "AI"


class CompanyBase(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    website: HttpUrl | None = None
    industry: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    priority: PriorityValue = PriorityValue.MEDIUM

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    website: HttpUrl | None = None
    industry: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=160)
    priority: PriorityValue | None = None
    is_watchlisted: bool | None = None


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    website: str | None
    industry: str | None
    location: str | None
    source: SourceValue
    priority: PriorityValue
    is_watchlisted: bool
    funding_score: int
    hiring_score: int
    ai_score: int
    location_score: int
    role_match_score: int
    total_score: int
    score_reason: str | None
    last_checked: datetime | None
    created_at: datetime


class JobCreate(BaseModel):
    company_id: int
    title: str = Field(min_length=2, max_length=240)
    location: str = Field(min_length=2, max_length=160)
    url: HttpUrl
    source: str = Field(default="MANUAL", max_length=80)
    posted_at: datetime | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    title: str
    location: str
    url: str
    source: str
    status: str
    posted_at: datetime | None
    discovered_at: datetime
    company: CompanyRead


class CompanySuggestion(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    website: str | None = None
    industry: str
    location: str
    funding_score: int = Field(ge=0, le=10)
    hiring_score: int = Field(ge=0, le=10)
    ai_score: int = Field(ge=0, le=10)
    location_score: int = Field(ge=0, le=10)
    role_match_score: int = Field(ge=0, le=10)
    reason: str = Field(min_length=10, max_length=500)


class SuggestionBatch(BaseModel):
    suggestions: list[CompanySuggestion] = Field(min_length=1, max_length=10)


class DiscoveryRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=10)


class DashboardStats(BaseModel):
    companies: int
    watchlisted: int
    jobs_found: int
    recruiters_found: int
    messages_ready: int = 0
    messages_sent: int = 0
    replies: int = 0
    referrals: int = 0
    interviews: int = 0

