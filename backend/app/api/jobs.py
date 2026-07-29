from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.core.dependencies import DbSession
from app.models import Company, Job
from app.schemas import JobCreate, JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(
    db: DbSession,
    today_only: bool = False,
) -> list[Job]:
    query = select(Job).options(joinedload(Job.company)).order_by(Job.discovered_at.desc())
    if today_only:
        since = datetime.now(UTC) - timedelta(days=1)
        query = query.where(Job.discovered_at >= since)
    return list(db.scalars(query).unique().all())


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: DbSession) -> Job:
    if not db.get(Company, payload.company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    job = Job(
        company_id=payload.company_id,
        title=payload.title,
        location=payload.location,
        url=str(payload.url),
        source=payload.source,
        posted_at=payload.posted_at,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Job URL already exists") from exc
    return db.scalar(select(Job).options(joinedload(Job.company)).where(Job.id == job.id))
