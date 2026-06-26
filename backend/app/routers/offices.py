from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Company, Office
from ..schemas import CompanyOut, OfficeOut

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/companies", response_model=List[CompanyOut])
def list_companies(db: Session = Depends(get_db)):
    return db.query(Company).order_by(Company.name).all()


@router.get("/offices", response_model=List[OfficeOut])
def list_offices(
    city: Optional[str] = Query(None, description="Фильтр по городу"),
    company_id: Optional[int] = Query(None, description="Фильтр по компании"),
    db: Session = Depends(get_db),
):
    q = db.query(Office)
    if city:
        q = q.filter(Office.city == city)
    if company_id:
        q = q.filter(Office.company_id == company_id)
    return q.order_by(Office.city, Office.name).all()
