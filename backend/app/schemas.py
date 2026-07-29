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


class AtsProviderValue(StrEnum):
    GREENHOUSE = "GREENHOUSE"
    LEVER = "LEVER"
    ASHBY = "ASHBY"


class AtsSourceUpsert(BaseModel):
    provider: AtsProviderValue
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip()


class AtsSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    provider: AtsProviderValue
    slug: str
    enabled: bool
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None


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
    ats_source: AtsSourceRead | None = None


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
    auto_shortlist: bool = False
    minimum_score: int = Field(default=35, ge=0, le=50)


class DiscoverySourceRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ats_source_id: int
    status: str
    jobs_seen: int
    jobs_matched: int
    jobs_created: int
    error: str | None
    started_at: datetime
    completed_at: datetime | None


class DiscoveryRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    companies_checked: int
    suggestions_created: int
    jobs_found: int
    error: str | None
    started_at: datetime
    completed_at: datetime | None
    source_runs: list[DiscoverySourceRunRead] = Field(default_factory=list)


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


class RecruiterCreate(BaseModel):
    company_id: int
    name: str = Field(min_length=2, max_length=160)
    linkedin_url: HttpUrl
    designation: str | None = Field(default=None, max_length=240)
    activity: str | None = Field(default=None, max_length=1000)
    mutuals: int = Field(default=0, ge=0, le=10000)

    @field_validator("linkedin_url")
    @classmethod
    def require_linkedin_url(cls, value: HttpUrl) -> HttpUrl:
        host = (value.host or "").casefold()
        if host != "linkedin.com" and not host.endswith(".linkedin.com"):
            raise ValueError("Use a linkedin.com profile URL")
        return value


class RecruiterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    linkedin_url: str
    designation: str | None
    activity: str | None
    mutuals: int
    reply_probability: int | None
    is_shortlisted: bool
    shortlisted_job_id: int | None
    created_at: datetime


class ShortlistRequest(BaseModel):
    job_id: int | None = None
    note: str | None = Field(default=None, max_length=1000)


class CandidateProfileUpdate(BaseModel):
    name: str = Field(default="Rahul Ranjan", min_length=2, max_length=160)
    resume_text: str = Field(min_length=100, max_length=50000)
    positioning: str | None = Field(default=None, max_length=5000)


class CandidateProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    resume_text: str
    positioning: str | None
    updated_at: datetime


class OutreachGenerateRequest(BaseModel):
    recruiter_id: int
    job_id: int
    extra_context: str | None = Field(default=None, max_length=5000)


class OutreachUpdate(BaseModel):
    body: str = Field(min_length=20, max_length=2000)


class OutreachRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recruiter_id: int
    job_id: int
    body: str
    rationale: str | None
    status: str
    delivery_mode: str
    delivery_error: str | None
    generated_at: datetime
    approved_at: datetime | None
    sent_at: datetime | None
    replied_at: datetime | None
    recruiter: RecruiterRead
    job: JobRead


class DeliveryCapabilities(BaseModel):
    automatic_linkedin_send: bool
    mode: str
    daily_limit: int
    sent_today: int
    reason: str | None


class OutreachAction(BaseModel):
    message: OutreachRead
    linkedin_url: str
    automatic_send_available: bool
