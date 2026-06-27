import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

import src.config as config
from src.errors import ApiError
from src.models.product import SKU, SKUCharacteristic, Product
from src.schemas.product import SKUCreateIn

# Maps internal event name → OpenAPI event_type enum
_EVENT_TYPE_MAP = {
    "CREATED": "PRODUCT_CREATED",
    "EDITED": "PRODUCT_EDITED",
    "DELETED": "PRODUCT_DELETED",
}


def _invalid(message: str) -> ApiError:
    return ApiError(400, "INVALID_REQUEST", message)


def _send_moderation_event(product_id: str, seller_id: str, event: str, product_json: dict | None = None, json_before: dict | None = None) -> None:
    if not config.MODERATION_URL or not config.B2B_TO_MOD_KEY:
        return
    event_type = _EVENT_TYPE_MAP.get(event, event)
    payload = {
        "event_type": event_type,
        "idempotency_key": str(uuid.uuid4()),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "product_id": product_id,
            "seller_id": seller_id,
            "json_before": json_before or {},
            "json_after": product_json or {},
        },
    }
    try:
        httpx.post(
            f"{config.MODERATION_URL}/api/v1/b2b/events",
            json=payload,
            headers={"X-Service-Key": config.B2B_TO_MOD_KEY},
            timeout=5.0,
        )
    except Exception:
        pass  # best-effort; не роллбэчим SKU при недоступности Moderation


def create_sku(db: Session, data: SKUCreateIn, seller_id: uuid.UUID) -> SKU:
    if not data.product_id:
        raise _invalid("product_id is required")

    product = db.get(Product, data.product_id)
    # 404 для несуществующего и чужого товара — не раскрываем существование
    if product is None or product.seller_id != str(seller_id):
        raise ApiError(404, "NOT_FOUND", "Product not found")

    if product.status == "HARD_BLOCKED":
        raise ApiError(403, "FORBIDDEN", "Cannot add SKU to hard-blocked product")

    if not data.name or not data.name.strip():
        raise _invalid("name is required")

    # images are OPTIONAL per openapi (SKUCreate.images has default []) — accept zero or more.
    images = data.effective_images

    # price is required, minimum 0 per openapi (SKUCreate.price minimum:0) — 0 is valid.
    if data.price is None or data.price < 0:
        raise _invalid("price must be a non-negative integer (kopecks)")
    # cost_price is optional and openapi sets no minimum — reject only negative values.
    if data.cost_price is not None and data.cost_price < 0:
        raise _invalid("cost_price must be a non-negative integer (kopecks)")
    if data.discount < 0:
        raise _invalid("discount must be >= 0")

    is_first_sku = len(product.skus) == 0
    pid, sid = product.id, product.seller_id  # сохраняем до commit

    sku = SKU(
        product_id=product.id,
        name=data.name.strip(),
        price=data.price,
        cost_price=data.cost_price,
        discount=data.discount,
        image=images[0].url if images else None,  # store first image URL (may be None: images optional)
    )
    sku.characteristics = [
        SKUCharacteristic(name=c.name, value=c.value) for c in data.characteristics
    ]
    db.add(sku)

    if product.status in ("MODERATED", "BLOCKED"):
        # Re-moderation: any new SKU on already-moderated product → back to review
        # (b2b-flows.md:257-264)
        # Capture json_before BEFORE commit while state is still accessible
        product_snapshot = {"id": product.id, "status": product.status, "title": product.title}
        product.status = "ON_MODERATION"
        db.add(product)
        db.commit()
        db.refresh(sku)
        _send_moderation_event(pid, sid, "EDITED", json_before=product_snapshot)
    elif is_first_sku and product.status == "CREATED":
        product.status = "ON_MODERATION"
        db.add(product)
        db.commit()
        db.refresh(sku)
        _send_moderation_event(pid, sid, "CREATED")
    else:
        db.commit()
        db.refresh(sku)

    return sku
