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
        "event": "PRODUCT_BLOCKED",
        "product_id": product.id,
        "sku_ids": [s.id for s in product.skus],
        "date": datetime.now(timezone.utc).isoformat(),
    }
    try:
        httpx.post(
            f"{config.B2C_URL}/api/v1/events/product",
            json=payload,
            headers={"X-Service-Key": config.B2B_TO_B2C_KEY},
            timeout=5.0,
        )
    except Exception:
        pass  # fire-and-forget


def apply_moderation_decision(db: Session, data: ModerationEventIn) -> None:
    # Идемпотентность: повторный запрос без изменений
    if db.query(ModerationEventLog).filter_by(idempotency_key=data.idempotency_key).first():
        return

    product = db.get(Product, data.product_id)
    if product is None:
        raise ApiError(404, "NOT_FOUND", "Product not found")

    # Удаляем старую причину блокировки (если есть) перед изменениями
    old_br_id = product.blocking_reason_id
    if old_br_id:
        old_br = db.get(BlockingReason, old_br_id)
        if old_br:
            product.blocking_reason_id = None
            db.flush()
            db.delete(old_br)
            db.flush()

    if data.status == "MODERATED":
        product.status = "MODERATED"
        product.blocked = False

    elif data.status == "BLOCKED":
        new_status = "HARD_BLOCKED" if data.hard_block else "BLOCKED"
        br_in = data.blocking_reason

        new_br = BlockingReason(
            title=br_in.title if br_in else "",
            comment=br_in.comment if br_in else None,
        )
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
        raise ApiError(400, "INVALID_REQUEST", f"Unknown status: {data.status}")

    db.add(ModerationEventLog(
        idempotency_key=data.idempotency_key,
        product_id=data.product_id,
    ))
    db.commit()

    # Каскад в B2C при блокировке (после commit)
    if data.status == "BLOCKED":
        db.refresh(product)
        _send_product_blocked_event(product)
