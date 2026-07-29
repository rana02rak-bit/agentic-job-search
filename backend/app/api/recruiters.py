from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.dependencies import DbSession
from app.models import Company, Job, Recruiter, RecruiterShortlist
from app.schemas import RecruiterCreate, RecruiterRead, ShortlistRequest
from app.services.recruiter_scoring import score_reply_probability

router = APIRouter(prefix="/recruiters", tags=["recruiters"])


def recruiter_query():
    return (
        select(Recruiter)
        .options(selectinload(Recruiter.shortlist))
        .execution_options(populate_existing=True)
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
        linkedin_url=str(payload.linkedin_url),
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
            detail="This LinkedIn profile is already stored for the company",
        ) from exc
    return db.scalar(recruiter_query().where(Recruiter.id == recruiter.id))


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
