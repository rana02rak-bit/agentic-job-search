from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.dependencies import DbSession
from app.models import Company, Job, Recruiter, RecruiterShortlist
from app.schemas import (
    ContactDiscoveryRequest,
    ContactDiscoveryResult,
    RecruiterCreate,
    RecruiterRead,
    ShortlistRequest,
)
from app.services.connectsafely import (
    ConnectSafelyUnavailable,
    discover_contacts,
)
from app.services.recruiter_scoring import score_reply_probability

router = APIRouter(prefix="/recruiters", tags=["recruiters"])


def recruiter_query():
    return (
        select(Recruiter)
        .options(selectinload(Recruiter.shortlist))
        .execution_options(populate_existing=True)
    )


def saved_people_for_company(
    db: DbSession,
    company_id: int,
    limit: int,
) -> list[Recruiter]:
    return list(
        db.scalars(
            recruiter_query()
            .where(Recruiter.company_id == company_id)
            .order_by(Recruiter.reply_probability.desc(), Recruiter.name)
            .limit(limit)
        ).all()
    )


@router.get("", response_model=list[RecruiterRead])
def list_recruiters(
    db: DbSession,
    company_id: int | None = None,
    shortlisted: bool | None = None,
) -> list[Recruiter]:
    query = recruiter_query()
    if company_id is not None:
        query = query.where(Recruiter.company_id == company_id)
    if shortlisted is True:
        query = query.join(Recruiter.shortlist)
    elif shortlisted is False:
        query = query.outerjoin(Recruiter.shortlist).where(RecruiterShortlist.id.is_(None))
    query = query.order_by(Recruiter.reply_probability.desc(), Recruiter.name)
    return list(db.scalars(query).all())


@router.post("", response_model=RecruiterRead, status_code=status.HTTP_201_CREATED)
def create_recruiter(payload: RecruiterCreate, db: DbSession) -> Recruiter:
    if not db.get(Company, payload.company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    recruiter = Recruiter(
        company_id=payload.company_id,
        name=" ".join(payload.name.split()),
        email=str(payload.email).casefold() if payload.email else None,
        email_status="MANUAL" if payload.email else None,
        linkedin_url=str(payload.linkedin_url) if payload.linkedin_url else None,
        source="MANUAL",
        designation=payload.designation,
        activity=payload.activity,
        mutuals=payload.mutuals,
        reply_probability=score_reply_probability(
            payload.designation,
            payload.activity,
            payload.mutuals,
        ),
    )
    db.add(recruiter)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This email or LinkedIn profile is already stored for the company",
        ) from exc
    return db.scalar(recruiter_query().where(Recruiter.id == recruiter.id))


@router.post("/discover", response_model=ContactDiscoveryResult)
def discover_recruiters(
    payload: ContactDiscoveryRequest,
    db: DbSession,
) -> ContactDiscoveryResult:
    company = db.get(Company, payload.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    job = db.get(Job, payload.job_id) if payload.job_id else None
    if payload.job_id and (not job or job.company_id != company.id):
        raise HTTPException(
            status_code=400,
            detail="Choose a job from the selected company",
        )
    try:
        discovered = discover_contacts(get_settings(), company, job, payload.limit)
    except ConnectSafelyUnavailable as exc:
        saved_people = saved_people_for_company(db, company.id, payload.limit)
        if not saved_people:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return ContactDiscoveryResult(
            company_id=company.id,
            discovered=0,
            stored=0,
            skipped_duplicates=0,
            people=saved_people,
            used_saved_people=True,
            warning=(
                "ConnectSafely is temporarily unavailable. "
                f"Showing {len(saved_people)} people already saved for {company.name}."
            ),
        )
    if not discovered:
        saved_people = saved_people_for_company(db, company.id, payload.limit)
        if saved_people:
            return ContactDiscoveryResult(
                company_id=company.id,
                discovered=0,
                stored=0,
                skipped_duplicates=0,
                people=saved_people,
                used_saved_people=True,
                warning=(
                    f"No new LinkedIn matches returned. Showing {len(saved_people)} people "
                    f"already saved for {company.name}."
                ),
            )

    stored_ids: list[int] = []
    result_ids: list[int] = []
    skipped_duplicates = 0
    for contact in discovered:
        existing = db.scalar(
            select(Recruiter).where(
                Recruiter.company_id == company.id,
                Recruiter.linkedin_url == contact.linkedin_url,
            )
        )
        if existing:
            result_ids.append(existing.id)
            skipped_duplicates += 1
            continue
        recruiter = Recruiter(
            company_id=company.id,
            name=contact.name,
            linkedin_url=contact.linkedin_url,
            source="CONNECTSAFELY",
            external_id=contact.external_id,
            designation=contact.designation,
            activity=contact.activity,
            mutuals=contact.mutuals,
            reply_probability=score_reply_probability(
                contact.designation,
                contact.activity,
                contact.mutuals,
            ),
        )
        db.add(recruiter)
        db.flush()
        if job:
            db.add(RecruiterShortlist(recruiter_id=recruiter.id, job_id=job.id))
        stored_ids.append(recruiter.id)
        result_ids.append(recruiter.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Contact discovery produced a duplicate record; run it again",
        ) from exc

    people = (
        list(
            db.scalars(
                recruiter_query()
                .where(Recruiter.id.in_(result_ids))
                .order_by(Recruiter.reply_probability.desc(), Recruiter.name)
            ).all()
        )
        if result_ids
        else []
    )
    return ContactDiscoveryResult(
        company_id=company.id,
        discovered=len(discovered),
        stored=len(stored_ids),
        skipped_duplicates=skipped_duplicates,
        people=people,
    )


@router.post("/{recruiter_id}/shortlist", response_model=RecruiterRead)
def shortlist_recruiter(
    recruiter_id: int,
    payload: ShortlistRequest,
    db: DbSession,
) -> Recruiter:
    recruiter = db.scalar(recruiter_query().where(Recruiter.id == recruiter_id))
    if not recruiter:
        raise HTTPException(status_code=404, detail="Person not found")
    if payload.job_id is not None:
        job = db.get(Job, payload.job_id)
        if not job or job.company_id != recruiter.company_id:
            raise HTTPException(
                status_code=400,
                detail="Choose a job from the same company as this person",
            )
    if recruiter.shortlist:
        recruiter.shortlist.job_id = payload.job_id
        recruiter.shortlist.note = payload.note
    else:
        db.add(
            RecruiterShortlist(
                recruiter_id=recruiter.id,
                job_id=payload.job_id,
                note=payload.note,
            )
        )
    db.commit()
    return db.scalar(recruiter_query().where(Recruiter.id == recruiter.id))


@router.delete("/{recruiter_id}/shortlist", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_shortlist(recruiter_id: int, db: DbSession) -> None:
    shortlist = db.scalar(
        select(RecruiterShortlist).where(RecruiterShortlist.recruiter_id == recruiter_id)
    )
    if not shortlist:
        raise HTTPException(status_code=404, detail="Person is not shortlisted")
    db.delete(shortlist)
    db.commit()
