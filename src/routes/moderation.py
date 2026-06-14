from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth import verify_service_key
from src.database import get_db
from src.schemas.product import ModerationEventIn
from src.services.moderation import apply_moderation_decision

router = APIRouter(prefix="/api/v1", tags=["Moderation Events"])


@router.post("/moderation/events", status_code=204)
def post_moderation_event(
    body: ModerationEventIn,
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_key),
):
    apply_moderation_decision(db, body)
