import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

import src.config as config
from src.errors import ApiError
from src.models.product import ReservationLog, SKU
from src.schemas.product import ReserveRequest, UnreserveRequest


def _send_out_of_stock_event(sku_id: str, product_id: str, available_quantity: int = 0) -> None:
    if not config.B2C_URL or not config.B2B_TO_B2C_KEY:
        return
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "event_type": "SKU_OUT_OF_STOCK",
        "idempotency_key": str(uuid.uuid4()),
        "occurred_at": now,
        "payload": {
            "sku_id": sku_id,
            "product_id": product_id,
            "available_quantity": available_quantity,
        },
    }
    try:
        httpx.post(
            f"{config.B2C_URL}/api/v1/b2b/events",
            json=payload,
            headers={"X-Service-Key": config.B2B_TO_B2C_KEY},
            timeout=5.0,
        )
    except Exception:
        pass  # best-effort; не роллбэчим резерв при недоступности B2C


def reserve_skus(db: Session, data: ReserveRequest) -> None:
    # Идемпотентность: повторный запрос — возвращаем без изменений
    if db.query(ReservationLog).filter_by(idempotency_key=data.idempotency_key).first():
        return

    if not data.items:
        raise ApiError(400, "INVALID_REQUEST", "items must not be empty")

    # Блокируем строки для атомарного обновления
    sku_ids = [item.sku_id for item in data.items]
    skus = {
        s.id: s
        for s in db.query(SKU).filter(SKU.id.in_(sku_ids)).with_for_update().all()
    }

    # Проверяем наличие и доступный остаток — до любых изменений
    for item in data.items:
        if item.quantity <= 0:
            raise ApiError(400, "INVALID_REQUEST", "quantity must be positive")
        sku = skus.get(item.sku_id)
        if sku is None:
            raise ApiError(404, "NOT_FOUND", f"SKU {item.sku_id} not found")
        available = sku.stock_quantity - sku.reserved_quantity
        if available < item.quantity:
            raise ApiError(
                409,
                "INSUFFICIENT_STOCK",
                f"SKU {item.sku_id}: requested {item.quantity}, available {available}",
            )

    # Применяем резервирование и фиксируем
    out_of_stock: list[tuple[str, str, int]] = []
    for item in data.items:
        sku = skus[item.sku_id]
        sku.reserved_quantity += item.quantity
        remaining = sku.stock_quantity - sku.reserved_quantity
        if remaining == 0:
            out_of_stock.append((sku.id, sku.product_id, 0))

    db.add(ReservationLog(idempotency_key=data.idempotency_key, operation="RESERVE"))
    db.commit()

    for sku_id, product_id, avail in out_of_stock:
        _send_out_of_stock_event(sku_id, product_id, avail)


def unreserve_skus(db: Session, data: UnreserveRequest) -> None:
    key = data.effective_key
    if not key:
        raise ApiError(400, "INVALID_REQUEST", "order_id or idempotency_key is required")
    if db.query(ReservationLog).filter_by(idempotency_key=key).first():
        return

    if not data.items:
        raise ApiError(400, "INVALID_REQUEST", "items must not be empty")

    sku_ids = [item.sku_id for item in data.items]
    skus = {
        s.id: s
        for s in db.query(SKU).filter(SKU.id.in_(sku_ids)).with_for_update().all()
    }

    for item in data.items:
        if item.quantity <= 0:
            raise ApiError(400, "INVALID_REQUEST", "quantity must be positive")
        if item.sku_id not in skus:
            raise ApiError(404, "NOT_FOUND", f"SKU {item.sku_id} not found")

    for item in data.items:
        sku = skus[item.sku_id]
        sku.reserved_quantity = max(0, sku.reserved_quantity - item.quantity)

    db.add(ReservationLog(idempotency_key=key, operation="UNRESERVE"))
    db.commit()
