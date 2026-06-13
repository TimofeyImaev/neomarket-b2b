import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

import src.config as config
from src.errors import ApiError
from src.models.product import SKU, SKUCharacteristic, Product
from src.schemas.product import SKUCreateIn


def _invalid(message: str) -> ApiError:
    return ApiError(400, "INVALID_REQUEST", message)


def _send_moderation_event(product_id: str, seller_id: str, event: str) -> None:
    if not config.MODERATION_URL or not config.B2B_TO_MOD_KEY:
        return
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "product_id": product_id,
        "seller_id": seller_id,
        "event": event,
        "date": datetime.now(timezone.utc).isoformat(),
    }
    try:
        httpx.post(
            f"{config.MODERATION_URL}/api/v1/events/product",
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
    if not data.image or not data.image.strip():
        raise _invalid("image is required")
    if data.price is None or data.price <= 0:
        raise _invalid("price must be a positive integer (kopecks)")
    if data.cost_price is None or data.cost_price <= 0:
        raise _invalid("cost_price must be a positive integer (kopecks)")
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
        image=data.image.strip(),
    )
    sku.characteristics = [
        SKUCharacteristic(name=c.name, value=c.value) for c in data.characteristics
    ]
    db.add(sku)

    if is_first_sku and product.status == "CREATED":
        product.status = "ON_MODERATION"
        db.add(product)
        db.commit()
        db.refresh(sku)
        _send_moderation_event(pid, sid, "CREATED")
    else:
        db.commit()
        db.refresh(sku)

    return sku
