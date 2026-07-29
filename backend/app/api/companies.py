from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.dependencies import DbSession
from app.models import Company, CompanySource
from app.schemas import CompanyCreate, CompanyRead, CompanyUpdate, SourceValue

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyRead])
def list_companies(
    db: DbSession,
    source: SourceValue | None = None,
    watchlisted: bool | None = None,
) -> list[Company]:
    query = select(Company).options(selectinload(Company.ats_source))
    if source:
        query = query.where(Company.source == source.value)
    if watchlisted is not None:
        query = query.where(Company.is_watchlisted == watchlisted)
    priority_order = case(
        (Company.priority == "HIGH", 1),
        (Company.priority == "MEDIUM", 2),
        else_=3,
    )
    return list(db.scalars(query.order_by(priority_order, Company.name)).all())


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, db: DbSession) -> Company:
    existing = db.scalar(
        select(Company).where(func.lower(Company.name) == payload.name.casefold())
    )
    if existing:
        if existing.is_watchlisted:
            raise HTTPException(status_code=409, detail="Company already exists")
        existing.is_watchlisted = True
        existing.source = CompanySource.USER.value
        existing.priority = payload.priority.value
        existing.website = str(payload.website) if payload.website else existing.website
        existing.industry = payload.industry or existing.industry
        existing.location = payload.location or existing.location
        db.commit()
        db.refresh(existing)
        return existing

    company = Company(
        name=payload.name,
        website=str(payload.website) if payload.website else None,
        industry=payload.industry,
        location=payload.location,
        priority=payload.priority.value,
        source=CompanySource.USER.value,
        is_watchlisted=True,
    )
    db.add(company)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Company already exists") from exc
    db.refresh(company)
    return company


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: DbSession,
) -> Company:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    changes = payload.model_dump(exclude_unset=True)
    if "website" in changes and changes["website"] is not None:
        changes["website"] = str(changes["website"])
    if "priority" in changes and changes["priority"] is not None:
        changes["priority"] = changes["priority"].value
    for field, value in changes.items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: int,
    db: DbSession,
    hard_delete: bool = Query(default=False),
) -> None:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if hard_delete:
        db.delete(company)
    else:
        company.is_watchlisted = False
    db.commit()
