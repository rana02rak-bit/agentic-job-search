from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.dependencies import DbSession
from app.models import Company, Job, Recruiter
from app.schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: DbSession) -> DashboardStats:
    return DashboardStats(
        companies=db.scalar(select(func.count()).select_from(Company)) or 0,
        watchlisted=(
            db.scalar(
                select(func.count()).select_from(Company).where(Company.is_watchlisted.is_(True))
            )
            or 0
        ),
        jobs_found=db.scalar(select(func.count()).select_from(Job)) or 0,
        recruiters_found=db.scalar(select(func.count()).select_from(Recruiter)) or 0,
    )
