from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.dependencies import DbSession
from app.models import Company, CompanySource, DiscoveryRun, Priority
from app.schemas import CompanyRead, DiscoveryRequest, DiscoveryRunRead
from app.services.ai_discovery import DiscoveryUnavailableError, generate_company_suggestions
from app.services.ats.runner import run_ats_discovery

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/sync", response_model=DiscoveryRunRead)
def sync_live_jobs(db: DbSession) -> DiscoveryRun:
    return run_ats_discovery(db)


@router.get("/runs", response_model=list[DiscoveryRunRead])
def list_discovery_runs(db: DbSession, limit: int = 10) -> list[DiscoveryRun]:
    safe_limit = min(max(limit, 1), 50)
    query = (
        select(DiscoveryRun)
        .options(selectinload(DiscoveryRun.source_runs))
        .order_by(DiscoveryRun.started_at.desc())
        .limit(safe_limit)
    )
    return list(db.scalars(query).all())


@router.post("/suggest", response_model=list[CompanyRead])
def suggest_companies(
    payload: DiscoveryRequest,
    db: DbSession,
) -> list[Company]:
    run = DiscoveryRun(status="RUNNING")
    db.add(run)
    db.commit()
    db.refresh(run)

    existing_names = list(db.scalars(select(Company.name)).all())
    try:
        batch = generate_company_suggestions(get_settings(), existing_names, payload.count)
        created: list[Company] = []
        existing_keys = {name.casefold() for name in existing_names}
        for item in batch.suggestions:
            if item.name.casefold() in existing_keys:
                continue
            company = Company(
                name=item.name,
                website=item.website,
                industry=item.industry,
                location=item.location,
                source=CompanySource.AI.value,
                priority=Priority.MEDIUM.value,
                is_watchlisted=False,
                funding_score=item.funding_score,
                hiring_score=item.hiring_score,
                ai_score=item.ai_score,
                location_score=item.location_score,
                role_match_score=item.role_match_score,
                score_reason=item.reason,
            )
            db.add(company)
            existing_keys.add(item.name.casefold())
            created.append(company)
        run = db.get(DiscoveryRun, run.id)
        run.status = "COMPLETED"
        run.companies_checked = len(existing_names)
        run.suggestions_created = len(created)
        run.completed_at = datetime.now(UTC)
        db.commit()
        for company in created:
            db.refresh(company)
        return created
    except DiscoveryUnavailableError as exc:
        run = db.get(DiscoveryRun, run.id)
        run.status = "FAILED"
        run.error = str(exc)
        run.completed_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
