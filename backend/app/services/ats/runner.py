from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AtsProvider,
    AtsSource,
    Company,
    DiscoveryRun,
    DiscoverySourceRun,
    Job,
    JobSource,
)
from app.services.ats.base import AtsJob
from app.services.ats.registry import fetch_jobs
from app.services.job_matching import is_target_job

Fetcher = Callable[[AtsProvider, str], list[AtsJob]]


def run_ats_discovery(db: Session, fetcher: Fetcher | None = None) -> DiscoveryRun:
    active_fetcher = fetcher or fetch_jobs
    run = DiscoveryRun(status="RUNNING")
    db.add(run)
    db.flush()

    priority_order = case(
        (Company.priority == "HIGH", 1),
        (Company.priority == "MEDIUM", 2),
        else_=3,
    )
    sources = list(
        db.scalars(
            select(AtsSource)
            .join(AtsSource.company)
            .options(selectinload(AtsSource.company))
            .where(AtsSource.enabled.is_(True), Company.is_watchlisted.is_(True))
            .order_by(priority_order, Company.name)
        ).all()
    )

    total_created = 0
    failures = 0
    for source in sources:
        source_run = DiscoverySourceRun(
            discovery_run_id=run.id,
            ats_source_id=source.id,
            status="RUNNING",
        )
        db.add(source_run)
        db.flush()
        checked_at = datetime.now(UTC)
        source.last_checked_at = checked_at
        source.company.last_checked = checked_at

        try:
            candidates = active_fetcher(AtsProvider(source.provider), source.slug)
            matched = [job for job in candidates if is_target_job(job.title, job.location)]
            created = _store_jobs(db, source, matched)
            total_created += created
            source_run.status = "COMPLETED"
            source_run.jobs_seen = len(candidates)
            source_run.jobs_matched = len(matched)
            source_run.jobs_created = created
            source_run.completed_at = datetime.now(UTC)
            source.last_success_at = source_run.completed_at
            source.last_error = None
        except Exception as exc:  # keep other configured sources running
            failures += 1
            error = str(exc)[:2000]
            source_run.status = "FAILED"
            source_run.error = error
            source_run.completed_at = datetime.now(UTC)
            source.last_error = error

    run.status = "COMPLETED_WITH_ERRORS" if failures else "COMPLETED"
    run.companies_checked = len(sources)
    run.jobs_found = total_created
    run.error = f"{failures} source(s) failed" if failures else None
    run.completed_at = datetime.now(UTC)
    db.commit()
    return _load_run(db, run.id)


def _store_jobs(db: Session, source: AtsSource, candidates: list[AtsJob]) -> int:
    created = 0
    for candidate in candidates:
        linked = db.scalar(
            select(JobSource).where(
                JobSource.ats_source_id == source.id,
                JobSource.external_id == candidate.external_id,
            )
        )
        if linked:
            continue

        job = db.scalar(select(Job).where(Job.url == candidate.url))
        if not job:
            job = Job(
                company_id=source.company_id,
                title=candidate.title,
                location=candidate.location,
                url=candidate.url,
                source=source.provider,
                posted_at=candidate.posted_at,
            )
            db.add(job)
            db.flush()
            created += 1

        db.add(
            JobSource(
                job_id=job.id,
                ats_source_id=source.id,
                external_id=candidate.external_id,
            )
        )
    return created


def _load_run(db: Session, run_id: int) -> DiscoveryRun:
    return db.scalar(
        select(DiscoveryRun)
        .options(selectinload(DiscoveryRun.source_runs))
        .where(DiscoveryRun.id == run_id)
    )
