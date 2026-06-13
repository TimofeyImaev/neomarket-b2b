from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth import verify_service_key
from src.database import get_db
from src.schemas.product import ReserveRequest, UnreserveRequest
from src.services.reserve import reserve_skus, unreserve_skus

router = APIRouter(prefix="/api/v1", tags=["Reserve"])


@router.post("/reserve", status_code=200)
def post_reserve(
    body: ReserveRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_key),
):
    reserve_skus(db, body)
    return {"status": "ok"}


@router.post("/unreserve", status_code=200)
def post_unreserve(
    body: UnreserveRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_key),
):
    unreserve_skus(db, body)
    return {"status": "ok"}
