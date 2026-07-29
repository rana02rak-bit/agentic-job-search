from datetime import UTC, datetime
from threading import Lock
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
from app.services.connectsafely import (
    ConnectSafelyUnavailable,
    get_account_status,
    send_linkedin_message,
)
from app.services.message_generator import (
    MessageGenerationUnavailable,
    generate_outreach_message,
)

router = APIRouter(prefix="/outreach", tags=["outreach"])
SEND_RESERVATION_LOCK = Lock()


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
    if not recruiter.linkedin_url:
        raise HTTPException(
            status_code=409,
            detail="This person has no LinkedIn profile URL.",
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
        subject=generated.subject,
        body=generated.body,
        rationale=generated.rationale,
        status=OutreachStatus.DRAFT.value,
        delivery_mode="CONNECTSAFELY",
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
    message.subject = payload.subject
    message.body = payload.body
    db.commit()
    return load_message(db, message.id)


@router.post("/messages/{message_id}/approve", response_model=OutreachAction)
def approve_message(message_id: int, db: DbSession) -> OutreachAction:
    message = load_message(db, message_id)
    if message.status != OutreachStatus.DRAFT.value:
        raise HTTPException(status_code=409, detail="Only draft messages can be approved")
    if not message.recruiter.linkedin_url:
        raise HTTPException(status_code=409, detail="Recipient LinkedIn profile is missing")
    message.status = OutreachStatus.APPROVED.value
    message.approved_at = datetime.now(UTC)
    db.commit()
    message = load_message(db, message.id)
    settings = get_settings()
    automatic_send_available = bool(
        settings.connectsafely_api_key and settings.connectsafely_account_id
    )
    if settings.connectsafely_api_key and not settings.connectsafely_account_id:
        try:
            automatic_send_available = get_account_status(settings).connected
        except ConnectSafelyUnavailable:
            automatic_send_available = False
    return OutreachAction(
        message=message,
        linkedin_url=message.recruiter.linkedin_url,
        automatic_send_available=automatic_send_available,
    )


@router.post("/messages/{message_id}/send", response_model=OutreachRead)
def send_message(message_id: int, db: DbSession) -> OutreachMessage:
    message = load_message(db, message_id)
    if message.status != OutreachStatus.APPROVED.value:
        raise HTTPException(status_code=409, detail="Approve the message before sending")
    settings = get_settings()
    if not settings.connectsafely_api_key:
        raise HTTPException(
            status_code=409,
            detail="Configure CONNECTSAFELY_API_KEY before sending",
        )
    if not message.recruiter.linkedin_url:
        raise HTTPException(status_code=409, detail="Recipient LinkedIn profile is missing")

    with SEND_RESERVATION_LOCK:
        if count_sent_today(db) >= settings.outreach_daily_send_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Daily LinkedIn limit of {settings.outreach_daily_send_limit} reached",
            )
        message.status = OutreachStatus.SENDING.value
        message.sent_at = datetime.now(UTC)
        message.delivery_error = None
        db.commit()

    try:
        provider_message_id, provider_thread_id = send_linkedin_message(
            settings,
            message.recruiter.linkedin_url,
            message.body,
            message.subject,
        )
    except ConnectSafelyUnavailable as exc:
        message.status = OutreachStatus.APPROVED.value
        message.sent_at = None
        message.delivery_error = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    message.status = OutreachStatus.SENT.value
    message.provider_message_id = provider_message_id
    message.provider_thread_id = provider_thread_id
    message.delivery_error = None
    db.commit()
    return load_message(db, message.id)


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
    connected = False
    account_name = None
    reason = "Add a fresh ConnectSafely API key locally, then connect LinkedIn."
    if settings.connectsafely_api_key:
        if settings.connectsafely_account_id:
            connected = True
            reason = "Approved DMs send through the configured LinkedIn account."
        else:
            try:
                account = get_account_status(settings)
                connected = account.connected
                account_name = account.name
                reason = (
                    f"Approved DMs send through {account.name or 'the connected LinkedIn account'}."
                    if connected
                    else "Connect your LinkedIn account in the ConnectSafely dashboard."
                )
            except ConnectSafelyUnavailable as exc:
                reason = str(exc)
    return DeliveryCapabilities(
        automatic_linkedin_send=connected,
        mode="CONNECTSAFELY",
        connectsafely_configured=bool(settings.connectsafely_api_key),
        account_connected=connected,
        account_name=account_name,
        daily_limit=settings.outreach_daily_send_limit,
        sent_today=count_sent_today(db),
        reason=reason,
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
