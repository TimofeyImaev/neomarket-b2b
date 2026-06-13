"""
US-B2B-09: Применение решения модерации к товару
DoD: https://contract.tochka-urfu.tech/quests/contraction-implement-us-b2b-09-apply-moderation
"""
import uuid
from unittest.mock import patch

from tests.conftest import SERVICE_HEADERS, TestingSession, auth_headers, valid_payload
from src.models.product import Product


def _create_product_on_moderation(client) -> tuple[str, dict]:
    seller_headers = auth_headers(str(uuid.uuid4()))
    resp = client.post("/api/v1/products", json=valid_payload(), headers=seller_headers)
    assert resp.status_code == 201
    product_id = resp.json()["id"]

    with patch("src.services.skus._send_moderation_event"):
        sku_resp = client.post(
            "/api/v1/skus",
            json={
                "product_id": product_id,
                "name": "Variant A",
                "price": 10000,
                "cost_price": 5000,
                "discount": 0,
                "image": "/s3/img.jpg",
                "characteristics": [],
            },
            headers=seller_headers,
        )
    assert sku_resp.status_code == 201

    # Убеждаемся, что статус ON_MODERATION
    db = TestingSession()
    product = db.get(Product, product_id)
    product.status = "ON_MODERATION"
    db.commit()
    db.close()

    return product_id, seller_headers


def _blocked_event(product_id: str, hard_block: bool = False, key: str | None = None) -> dict:
    return {
        "idempotency_key": key or str(uuid.uuid4()),
        "product_id": product_id,
        "status": "BLOCKED",
        "hard_block": hard_block,
        "blocking_reason": {
            "id": str(uuid.uuid4()),
            "title": "Описание не соответствует товару",
            "comment": "Фото и описание расходятся",
        },
        "field_reports": [
            {"field_name": "description", "sku_id": None, "comment": "Неверное описание"},
        ],
    }


# ── DoD тесты ────────────────────────────────────────────────────────────────

def test_moderated_event_clears_blocking_data(client):
    product_id, _ = _create_product_on_moderation(client)

    # Сначала блокируем
    client.post(
        "/api/v1/events/moderation",
        json=_blocked_event(product_id),
        headers=SERVICE_HEADERS,
    )

    # Затем одобряем
    resp = client.post(
        "/api/v1/events/moderation",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "product_id": product_id,
            "status": "MODERATED",
        },
        headers=SERVICE_HEADERS,
    )
    assert resp.status_code == 200

    db = TestingSession()
    product = db.get(Product, product_id)
    db.close()
    assert product.status == "MODERATED"
    assert product.blocked is False
    assert product.blocking_reason_id is None


def test_blocked_soft_saves_field_reports(client):
    product_id, _ = _create_product_on_moderation(client)

    with patch("src.services.moderation._send_product_blocked_event") as mock_event:
        resp = client.post(
            "/api/v1/events/moderation",
            json=_blocked_event(product_id, hard_block=False),
            headers=SERVICE_HEADERS,
        )
    assert resp.status_code == 200
    mock_event.assert_called_once()

    db = TestingSession()
    product = db.get(Product, product_id)
    db.close()
    assert product.status == "BLOCKED"
    assert product.blocked is True
    assert product.blocking_reason_id is not None

    # Проверяем что field_reports сохранены через связь
    db = TestingSession()
    product = db.get(Product, product_id)
    br = product.blocking_reason
    assert br is not None
    assert len(br.field_reports) == 1
    assert br.field_reports[0].field == "description"
    db.close()


def test_blocked_hard_sets_terminal_status(client):
    product_id, _ = _create_product_on_moderation(client)

    with patch("src.services.moderation._send_product_blocked_event") as mock_event:
        resp = client.post(
            "/api/v1/events/moderation",
            json=_blocked_event(product_id, hard_block=True),
            headers=SERVICE_HEADERS,
        )
    assert resp.status_code == 200
    mock_event.assert_called_once()

    db = TestingSession()
    product = db.get(Product, product_id)
    db.close()
    assert product.status == "HARD_BLOCKED"
    assert product.blocked is True


def test_hard_blocked_product_rejects_seller_edits(client):
    product_id, seller_headers = _create_product_on_moderation(client)

    # Переводим в HARD_BLOCKED
    with patch("src.services.moderation._send_product_blocked_event"):
        client.post(
            "/api/v1/events/moderation",
            json=_blocked_event(product_id, hard_block=True),
            headers=SERVICE_HEADERS,
        )

    # PUT должен возвращать 403
    put_resp = client.put(
        f"/api/v1/products/{product_id}",
        json=valid_payload(),
        headers=seller_headers,
    )
    assert put_resp.status_code == 403
    assert put_resp.json()["code"] == "FORBIDDEN"

    # DELETE должен возвращать 403
    del_resp = client.delete(
        f"/api/v1/products/{product_id}",
        headers=seller_headers,
    )
    assert del_resp.status_code == 403
    assert del_resp.json()["code"] == "FORBIDDEN"


def test_duplicate_event_same_idempotency_key_no_side_effects(client):
    product_id, _ = _create_product_on_moderation(client)
    key = str(uuid.uuid4())

    with patch("src.services.moderation._send_product_blocked_event") as mock_event:
        resp1 = client.post(
            "/api/v1/events/moderation",
            json=_blocked_event(product_id, hard_block=False, key=key),
            headers=SERVICE_HEADERS,
        )
        resp2 = client.post(
            "/api/v1/events/moderation",
            json=_blocked_event(product_id, hard_block=False, key=key),
            headers=SERVICE_HEADERS,
        )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Каскад вызван только один раз
    assert mock_event.call_count == 1

    db = TestingSession()
    product = db.get(Product, product_id)
    db.close()
    assert product.status == "BLOCKED"


# ── Дополнительные сценарии ───────────────────────────────────────────────────

def test_missing_service_key_returns_401(client):
    resp = client.post(
        "/api/v1/events/moderation",
        json={"idempotency_key": str(uuid.uuid4()), "product_id": str(uuid.uuid4()), "status": "MODERATED"},
    )
    assert resp.status_code == 401
