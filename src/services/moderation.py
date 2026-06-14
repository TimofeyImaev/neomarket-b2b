import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

import src.config as config
from src.errors import ApiError
from src.models.product import BlockingReason, FieldReport, ModerationEventLog, Product
from src.schemas.product import ModerationEventIn


def _send_product_blocked_event(product: Product) -> None:
    if not config.B2C_URL or not config.B2B_TO_B2C_KEY:
        return
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "event_type": "PRODUCT_BLOCKED",
        "product_id": product.id,
        "sku_ids": [s.id for s in product.skus],
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        httpx.post(
            f"{config.B2C_URL}/api/v1/b2b/events",
            json=payload,
            headers={"X-Service-Key": config.B2B_TO_B2C_KEY},
            timeout=5.0,
        )
    except Exception:
        pass


def apply_moderation_decision(db: Session, data: ModerationEventIn) -> None:
    if db.query(ModerationEventLog).filter_by(idempotency_key=data.idempotency_key).first():
        return

    product = db.get(Product, data.product_id)
    if product is None:
        raise ApiError(404, "NOT_FOUND", "Product not found")

    old_br_id = product.blocking_reason_id
    if old_br_id:
        old_br = db.get(BlockingReason, old_br_id)
        if old_br:
            product.blocking_reason_id = None
            db.flush()
            db.delete(old_br)
            db.flush()

    if data.event_type == "MODERATED":
        product.status = "MODERATED"
        product.blocked = False

    elif data.event_type == "BLOCKED":
        new_status = "HARD_BLOCKED" if data.hard_block else "BLOCKED"
        br_id = data.blocking_reason_id or str(uuid.uuid4())
        new_br = BlockingReason(id=br_id, title="", comment=None)
        db.add(new_br)
        db.flush()

        for fr_in in data.field_reports:
            db.add(FieldReport(
                blocking_reason_id=new_br.id,
                field=fr_in.field_name,
                message=fr_in.comment,
                sku_id=fr_in.sku_id,
            ))

        product.status = new_status
        product.blocked = True
        product.blocking_reason_id = new_br.id

    else:
        raise ApiError(400, "INVALID_REQUEST", f"Unknown event_type: {data.event_type}")

    db.add(ModerationEventLog(
        idempotency_key=data.idempotency_key,
        product_id=data.product_id,
    ))
    db.commit()

    if data.event_type == "BLOCKED":
        db.refresh(product)
        _send_product_blocked_event(product)
