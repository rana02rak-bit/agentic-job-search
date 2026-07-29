from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.dependencies import DbSession
from app.models import (
    CandidateProfile,
    Job,
    OutreachMessage,
    OutreachStatus,
    Recruiter,
)
from app.schemas import (
    CandidateProfileRead,
    CandidateProfileUpdate,
    DeliveryCapabilities,
    OutreachAction,
    OutreachGenerateRequest,
    OutreachRead,
    OutreachUpdate,
)
from app.services.message_generator import (
    MessageGenerationUnavailable,
    generate_outreach_message,
)

router = APIRouter(prefix="/outreach", tags=["outreach"])


def outreach_query():
    return select(OutreachMessage).options(
        selectinload(OutreachMessage.recruiter).selectinload(Recruiter.shortlist),
        selectinload(OutreachMessage.job).selectinload(Job.company),
    )


def load_message(db: DbSession, message_id: int) -> OutreachMessage:
    message = db.scalar(outreach_query().where(OutreachMessage.id == message_id))
    if not message:
        raise HTTPException(status_code=404, detail="Outreach message not found")
    return message


@router.get("/profile", response_model=CandidateProfileRead)
def get_candidate_profile(db: DbSession) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).order_by(CandidateProfile.id).limit(1))
    if not profile:
        raise HTTPException(status_code=404, detail="Resume profile is not configured")
    return profile


@router.put("/profile", response_model=CandidateProfileRead)
def save_candidate_profile(
    payload: CandidateProfileUpdate,
    db: DbSession,
) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).order_by(CandidateProfile.id).limit(1))
    if profile:
        profile.name = payload.name
        profile.resume_text = payload.resume_text
        profile.positioning = payload.positioning
    else:
        profile = CandidateProfile(**payload.model_dump())
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/messages", response_model=list[OutreachRead])
def list_messages(
    db: DbSession,
    message_status: str | None = None,
) -> list[OutreachMessage]:
    query = outreach_query().order_by(OutreachMessage.generated_at.desc())
    if message_status:
        query = query.where(OutreachMessage.status == message_status.upper())
    return list(db.scalars(query).all())


@router.post(
    "/messages",
    response_model=OutreachRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_message(
    payload: OutreachGenerateRequest,
    db: DbSession,
) -> OutreachMessage:
    profile = db.scalar(select(CandidateProfile).order_by(CandidateProfile.id).limit(1))
    if not profile:
        raise HTTPException(
            status_code=409,
            detail="Save Rahul's resume profile before generating a message",
        )
    recruiter = db.get(Recruiter, payload.recruiter_id)
    job = db.scalar(
        select(Job).options(selectinload(Job.company)).where(Job.id == payload.job_id)
    )
    if not recruiter:
        raise HTTPException(status_code=404, detail="Person not found")
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if recruiter.company_id != job.company_id:
        raise HTTPException(
            status_code=400,
            detail="The person and job must belong to the same company",
        )
    try:
        generated = generate_outreach_message(
            get_settings(),
            profile,
            job,
            recruiter,
            payload.extra_context,
        )
    except MessageGenerationUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    message = OutreachMessage(
        recruiter_id=recruiter.id,
        job_id=job.id,
        body=generated.body,
        rationale=generated.rationale,
        status=OutreachStatus.DRAFT.value,
        delivery_mode=get_settings().linkedin_send_mode.upper(),
    )
    db.add(message)
    db.commit()
    return load_message(db, message.id)


@router.patch("/messages/{message_id}", response_model=OutreachRead)
def edit_message(
    message_id: int,
    payload: OutreachUpdate,
    db: DbSession,
) -> OutreachMessage:
    message = load_message(db, message_id)
    if message.status != OutreachStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail="Only draft messages can be edited")
    message.body = payload.body
    db.commit()
    return load_message(db, message.id)


@router.post("/messages/{message_id}/approve", response_model=OutreachAction)
def approve_message(message_id: int, db: DbSession) -> OutreachAction:
    message = load_message(db, message_id)
    if message.status != OutreachStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail="Only draft messages can be approved")
    message.status = OutreachStatus.APPROVED.value
    message.approved_at = datetime.now(UTC)
    db.commit()
    message = load_message(db, message.id)
    return OutreachAction(
        message=message,
        linkedin_url=message.recruiter.linkedin_url,
        automatic_send_available=False,
    )


@router.post("/messages/{message_id}/send", response_model=OutreachRead)
def send_message(message_id: int, db: DbSession) -> OutreachMessage:
    message = load_message(db, message_id)
    if message.status != OutreachStatus.APPROVED.value:
        raise HTTPException(status_code=409, detail="Approve the message before sending")
    settings = get_settings()
    if settings.linkedin_send_mode.casefold() != "partner_api":
        message.delivery_error = (
            "Automatic LinkedIn sending requires approved LinkedIn partner API access. "
            "Use Copy + Open LinkedIn, then mark the message sent."
        )
        db.commit()
        raise HTTPException(status_code=409, detail=message.delivery_error)
    raise HTTPException(
        status_code=503,
        detail="LinkedIn partner sender credentials and endpoint are not configured",
    )


@router.post("/messages/{message_id}/mark-sent", response_model=OutreachRead)
def mark_message_sent(message_id: int, db: DbSession) -> OutreachMessage:
    message = load_message(db, message_id)
    if message.status != OutreachStatus.APPROVED.value:
        raise HTTPException(status_code=409, detail="Approve the message before marking it sent")
    settings = get_settings()
    sent_today = count_sent_today(db)
    if sent_today >= settings.outreach_daily_send_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily outreach limit of {settings.outreach_daily_send_limit} reached",
        )
    message.status = OutreachStatus.SENT.value
    message.sent_at = datetime.now(UTC)
    message.delivery_error = None
    db.commit()
    return load_message(db, message.id)


@router.post("/messages/{message_id}/mark-replied", response_model=OutreachRead)
def mark_message_replied(message_id: int, db: DbSession) -> OutreachMessage:
    message = load_message(db, message_id)
    if message.status != OutreachStatus.SENT.value:
        raise HTTPException(status_code=409, detail="Only sent messages can be marked replied")
    message.status = OutreachStatus.REPLIED.value
    message.replied_at = datetime.now(UTC)
    db.commit()
    return load_message(db, message.id)


@router.get("/capabilities", response_model=DeliveryCapabilities)
def delivery_capabilities(db: DbSession) -> DeliveryCapabilities:
    settings = get_settings()
    return DeliveryCapabilities(
        automatic_linkedin_send=False,
        mode=settings.linkedin_send_mode.upper(),
        daily_limit=settings.outreach_daily_send_limit,
        sent_today=count_sent_today(db),
        reason="Automatic LinkedIn messaging needs approved partner API access.",
    )


def count_sent_today(db: DbSession) -> int:
    timezone = ZoneInfo(get_settings().discovery_timezone)
    local_now = datetime.now(timezone)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    since = local_midnight.astimezone(UTC)
    return (
        db.scalar(
            select(func.count())
            .select_from(OutreachMessage)
            .where(OutreachMessage.sent_at >= since)
        )
        or 0
    )
