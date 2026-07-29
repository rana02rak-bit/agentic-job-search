from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class CompanySource(StrEnum):
    USER = "USER"
    AI = "AI"


class Priority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class JobStatus(StrEnum):
    NEW = "NEW"
    SAVED = "SAVED"
    APPLIED = "APPLIED"
    HIDDEN = "HIDDEN"


class AtsProvider(StrEnum):
    GREENHOUSE = "GREENHOUSE"
    LEVER = "LEVER"
    ASHBY = "ASHBY"


class OutreachStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SENT = "SENT"
    REPLIED = "REPLIED"
    REJECTED = "REJECTED"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(500))
    industry: Mapped[str | None] = mapped_column(String(160))
    location: Mapped[str | None] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(20), default=CompanySource.USER.value, index=True)
    priority: Mapped[str] = mapped_column(String(20), default=Priority.MEDIUM.value, index=True)
    is_watchlisted: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    funding_score: Mapped[int] = mapped_column(Integer, default=0)
    hiring_score: Mapped[int] = mapped_column(Integer, default=0)
    ai_score: Mapped[int] = mapped_column(Integer, default=0)
    location_score: Mapped[int] = mapped_column(Integer, default=0)
    role_match_score: Mapped[int] = mapped_column(Integer, default=0)
    score_reason: Mapped[str | None] = mapped_column(Text)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    jobs: Mapped[list["Job"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    recruiters: Mapped[list["Recruiter"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    ats_source: Mapped["AtsSource | None"] = relationship(
        back_populates="company", cascade="all, delete-orphan", uselist=False
    )

    @property
    def total_score(self) -> int:
        return (
            self.funding_score
            + self.hiring_score
            + self.ai_score
            + self.location_score
            + self.role_match_score
        )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("url", name="uq_jobs_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(240), index=True)
    location: Mapped[str] = mapped_column(String(160), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    source: Mapped[str] = mapped_column(String(80), default="MANUAL")
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.NEW.value, index=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    company: Mapped[Company] = relationship(back_populates="jobs")
    source_links: Mapped[list["JobSource"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    outreach_messages: Mapped[list["OutreachMessage"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class AtsSource(Base):
    __tablename__ = "ats_sources"
    __table_args__ = (UniqueConstraint("company_id", name="uq_ats_source_company"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32), index=True)
    slug: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    company: Mapped[Company] = relationship(back_populates="ats_source")
    job_links: Mapped[list["JobSource"]] = relationship(
        back_populates="ats_source", cascade="all, delete-orphan"
    )
    source_runs: Mapped[list["DiscoverySourceRun"]] = relationship(
        back_populates="ats_source", cascade="all, delete-orphan"
    )


class JobSource(Base):
    __tablename__ = "job_sources"
    __table_args__ = (
        UniqueConstraint("ats_source_id", "external_id", name="uq_job_source_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    ats_source_id: Mapped[int] = mapped_column(ForeignKey("ats_sources.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="source_links")
    ats_source: Mapped[AtsSource] = relationship(back_populates="job_links")


class Recruiter(Base):
    __tablename__ = "recruiters"
    __table_args__ = (
        UniqueConstraint("company_id", "linkedin_url", name="uq_recruiter_company_linkedin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    linkedin_url: Mapped[str] = mapped_column(String(1000))
    designation: Mapped[str | None] = mapped_column(String(240))
    activity: Mapped[str | None] = mapped_column(Text)
    mutuals: Mapped[int] = mapped_column(Integer, default=0)
    reply_probability: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Company] = relationship(back_populates="recruiters")
    shortlist: Mapped["RecruiterShortlist | None"] = relationship(
        back_populates="recruiter", cascade="all, delete-orphan", uselist=False
    )
    outreach_messages: Mapped[list["OutreachMessage"]] = relationship(
        back_populates="recruiter", cascade="all, delete-orphan"
    )

    @property
    def is_shortlisted(self) -> bool:
        return self.shortlist is not None

    @property
    def shortlisted_job_id(self) -> int | None:
        return self.shortlist.job_id if self.shortlist else None


class RecruiterShortlist(Base):
    __tablename__ = "recruiter_shortlists"
    __table_args__ = (UniqueConstraint("recruiter_id", name="uq_shortlist_recruiter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    recruiter_id: Mapped[int] = mapped_column(
        ForeignKey("recruiters.id", ondelete="CASCADE")
    )
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    recruiter: Mapped[Recruiter] = relationship(back_populates="shortlist")
    job: Mapped[Job | None] = relationship()


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="Rahul Ranjan")
    resume_text: Mapped[str] = mapped_column(Text)
    positioning: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    recruiter_id: Mapped[int] = mapped_column(
        ForeignKey("recruiters.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), default=OutreachStatus.DRAFT.value, index=True
    )
    delivery_mode: Mapped[str] = mapped_column(String(32), default="MANUAL")
    delivery_error: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recruiter: Mapped[Recruiter] = relationship(back_populates="outreach_messages")
    job: Mapped[Job] = relationship(back_populates="outreach_messages")


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    companies_checked: Mapped[int] = mapped_column(Integer, default=0)
    suggestions_created: Mapped[int] = mapped_column(Integer, default=0)
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_runs: Mapped[list["DiscoverySourceRun"]] = relationship(
        back_populates="discovery_run", cascade="all, delete-orphan"
    )


class DiscoverySourceRun(Base):
    __tablename__ = "discovery_source_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    discovery_run_id: Mapped[int] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE")
    )
    ats_source_id: Mapped[int] = mapped_column(ForeignKey("ats_sources.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    jobs_seen: Mapped[int] = mapped_column(Integer, default=0)
    jobs_matched: Mapped[int] = mapped_column(Integer, default=0)
    jobs_created: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    discovery_run: Mapped[DiscoveryRun] = relationship(back_populates="source_runs")
    ats_source: Mapped[AtsSource] = relationship(back_populates="source_runs")
