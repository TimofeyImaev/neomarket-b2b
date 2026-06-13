"""
US-B2B-05: Просмотр карточки товара и причин блокировки
DoD: https://contract.tochka-urfu.tech/quests/contraction-implement-us-b2b-05-view-product-card
"""
import uuid
from unittest.mock import patch

from tests.conftest import CATEGORY_ID, TestingSession, auth_headers, valid_payload
from src.models.product import BlockingReason, FieldReport, Product


SELLER_ID = str(uuid.uuid4())
SELLER_HEADERS = auth_headers(SELLER_ID)


def _create_product(client) -> str:
    resp = client.post(
        "/api/v1/products",
        json=valid_payload(),
        headers=SELLER_HEADERS,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _set_status(product_id: str, status: str) -> None:
    db = TestingSession()
    product = db.get(Product, product_id)
    product.status = status
    db.commit()
    db.close()


# ── DoD тесты ────────────────────────────────────────────────────────────────

def test_get_moderated_product_returns_full_payload(client):
    product_id = _create_product(client)
    _set_status(product_id, "MODERATED")

    resp = client.get(f"/api/v1/products/{product_id}", headers=SELLER_HEADERS)
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "MODERATED"
    assert body["blocking_reason"] is None
    assert body["blocked"] is False
    assert body["field_reports"] == []
    for field in (
        "id", "seller_id", "category_id", "title", "slug", "description",
        "status", "deleted", "blocked", "blocking_reason", "field_reports",
        "moderator_comment", "images", "characteristics", "skus",
        "created_at", "updated_at",
    ):
        assert field in body, f"missing field: {field}"


def test_get_blocked_product_returns_blocking_reason_and_field_reports(client):
    product_id = _create_product(client)

    db = TestingSession()
    br = BlockingReason(title="Нарушение правил площадки")
    br.field_reports = [
        FieldReport(field="title", message="Слишком короткое название"),
        FieldReport(field="description", message="Описание содержит запрещённые слова"),
    ]
    db.add(br)
    db.commit()

    product = db.get(Product, product_id)
    product.status = "BLOCKED"
    product.blocked = True
    product.blocking_reason_id = br.id
    db.commit()
    db.close()

    resp = client.get(f"/api/v1/products/{product_id}", headers=SELLER_HEADERS)
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "BLOCKED"
    assert body["blocked"] is True
    assert body["blocking_reason"]["title"] == "Нарушение правил площадки"
    # field_reports — top-level поле продукта (не вложено в blocking_reason)
    reports = body["field_reports"]
    assert len(reports) == 2
    fields = {r["field_name"] for r in reports}
    assert "title" in fields
    assert "description" in fields


def test_get_others_product_returns_404(client):
    other_headers = auth_headers()  # другой продавец
    resp = client.post("/api/v1/products", json=valid_payload(), headers=other_headers)
    assert resp.status_code == 201
    product_id = resp.json()["id"]

    resp = client.get(f"/api/v1/products/{product_id}", headers=SELLER_HEADERS)
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_get_nonexistent_returns_404(client):
    resp = client.get(f"/api/v1/products/{uuid.uuid4()}", headers=SELLER_HEADERS)
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


# ── Дополнительные сценарии ───────────────────────────────────────────────────

def test_get_product_unauthorized_returns_401(client):
    resp = client.get(f"/api/v1/products/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_get_product_skus_include_cost_price_and_reserved_quantity(client):
    product_id = _create_product(client)
    with patch("src.services.skus._send_moderation_event"):
        sku_resp = client.post(
            "/api/v1/skus",
            json={
                "product_id": product_id,
                "name": "256GB Black",
                "price": 12999000,
                "cost_price": 9500000,
                "discount": 0,
                "image": "/s3/img.jpg",
                "characteristics": [],
            },
            headers=SELLER_HEADERS,
        )
    assert sku_resp.status_code == 201

    resp = client.get(f"/api/v1/products/{product_id}", headers=SELLER_HEADERS)
    assert resp.status_code == 200
    skus = resp.json()["skus"]
    assert len(skus) == 1
    assert skus[0]["cost_price"] == 9500000
    assert "reserved_quantity" in skus[0]
