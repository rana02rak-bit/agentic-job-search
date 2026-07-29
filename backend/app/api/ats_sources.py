from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import DbSession
from app.models import AtsSource, Company
from app.schemas import AtsSourceRead, AtsSourceUpsert

router = APIRouter(prefix="/companies", tags=["ATS sources"])


@router.get("/{company_id}/ats-source", response_model=AtsSourceRead)
def get_ats_source(company_id: int, db: DbSession) -> AtsSource:
    source = db.scalar(select(AtsSource).where(AtsSource.company_id == company_id))
    if not source:
        raise HTTPException(status_code=404, detail="ATS source not configured")
    return source


@router.put("/{company_id}/ats-source", response_model=AtsSourceRead)
def upsert_ats_source(
    company_id: int,
    payload: AtsSourceUpsert,
    db: DbSession,
) -> AtsSource:
    if not db.get(Company, company_id):
        raise HTTPException(status_code=404, detail="Company not found")

    source = db.scalar(select(AtsSource).where(AtsSource.company_id == company_id))
    if source:
        source.provider = payload.provider.value
        source.slug = payload.slug
        source.enabled = True
        source.last_error = None
    else:
        source = AtsSource(
            company_id=company_id,
            provider=payload.provider.value,
            slug=payload.slug,
            enabled=True,
        )
        db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/{company_id}/ats-source", status_code=status.HTTP_204_NO_CONTENT)
def delete_ats_source(company_id: int, db: DbSession) -> None:
    source = db.scalar(select(AtsSource).where(AtsSource.company_id == company_id))
    if not source:
        raise HTTPException(status_code=404, detail="ATS source not configured")
    source.enabled = False
    db.commit()
