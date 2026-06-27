"""
US-B2B-02: Добавление варианта товара (SKU)
DoD: https://contract.tochka-urfu.tech/quests/contraction-implement-us-b2b-02-add-sku
"""
import uuid
from unittest.mock import patch

from tests.conftest import CATEGORY_ID, TestingSession, auth_headers
from src.models.product import Product


SELLER_ID = str(uuid.uuid4())
SELLER_HEADERS = auth_headers(SELLER_ID)


def _create_product(client, status: str = "CREATED") -> str:
    resp = client.post(
        "/api/v1/products",
        json={
            "title": "Test Product",
            "description": "Test description",
            "category_id": CATEGORY_ID,
            "images": [{"url": "/s3/test.jpg", "ordering": 0}],
        },
        headers=SELLER_HEADERS,
    )
    assert resp.status_code == 201, resp.text
    product_id = resp.json()["id"]

    if status != "CREATED":
        db = TestingSession()
        product = db.get(Product, product_id)
        product.status = status
        db.commit()
        db.close()

    return product_id


def _sku_payload(product_id: str) -> dict:
    return {
        "product_id": product_id,
        "name": "256GB Black",
        "price": 12999000,
        "cost_price": 9500000,
        "discount": 0,
        "images": [{"url": "/s3/iphone15-black-256.jpg", "ordering": 0}],
        "characteristics": [{"name": "Цвет", "value": "Чёрный"}],
    }


# ── DoD тесты ────────────────────────────────────────────────────────────────

def test_first_sku_transitions_product_to_on_moderation(client):
    product_id = _create_product(client)
    with patch("src.services.skus._send_moderation_event"):
        resp = client.post("/api/v1/skus", json=_sku_payload(product_id), headers=SELLER_HEADERS)
    assert resp.status_code == 201

    db = TestingSession()
    product = db.get(Product, product_id)
    db.close()
    assert product.status == "ON_MODERATION"


def test_first_sku_emits_created_event_to_moderation(client):
    product_id = _create_product(client)
    with patch("src.services.skus._send_moderation_event") as mock_send:
        resp = client.post("/api/v1/skus", json=_sku_payload(product_id), headers=SELLER_HEADERS)
    assert resp.status_code == 201
    mock_send.assert_called_once()
    product_id_arg, seller_id_arg, event_arg = mock_send.call_args.args
    assert event_arg == "CREATED"
    assert product_id_arg == product_id


def test_second_sku_no_state_change(client):
    product_id = _create_product(client)
    with patch("src.services.skus._send_moderation_event"):
        client.post("/api/v1/skus", json=_sku_payload(product_id), headers=SELLER_HEADERS)

    payload2 = {**_sku_payload(product_id), "name": "512GB Black"}
    with patch("src.services.skus._send_moderation_event") as mock_send:
        resp = client.post("/api/v1/skus", json=payload2, headers=SELLER_HEADERS)
    assert resp.status_code == 201
    mock_send.assert_not_called()

    db = TestingSession()
    product = db.get(Product, product_id)
    db.close()
    assert product.status == "ON_MODERATION"


def test_add_sku_to_hard_blocked_returns_403(client):
    product_id = _create_product(client, status="HARD_BLOCKED")
    resp = client.post("/api/v1/skus", json=_sku_payload(product_id), headers=SELLER_HEADERS)
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"


def test_missing_image_is_accepted(client):
    """images are OPTIONAL per openapi (SKUCreate.images default []) — omitting them is valid (201)."""
    product_id = _create_product(client)
    payload = {k: v for k, v in _sku_payload(product_id).items() if k != "images"}
    with patch("src.services.skus._send_moderation_event"):
        resp = client.post("/api/v1/skus", json=payload, headers=SELLER_HEADERS)
    assert resp.status_code == 201, resp.text
    assert resp.json()["images"] == []


def test_price_zero_is_accepted(client):
    """price minimum is 0 per openapi (SKUCreate.price minimum:0) — price 0 must be accepted."""
    product_id = _create_product(client)
    payload = {**_sku_payload(product_id), "price": 0}
    with patch("src.services.skus._send_moderation_event"):
        resp = client.post("/api/v1/skus", json=payload, headers=SELLER_HEADERS)
    assert resp.status_code == 201, resp.text
    assert resp.json()["price"] == 0


def test_cost_price_zero_is_accepted(client):
    """cost_price has no minimum in openapi — 0 must be accepted."""
    product_id = _create_product(client)
    payload = {**_sku_payload(product_id), "cost_price": 0}
    with patch("src.services.skus._send_moderation_event"):
        resp = client.post("/api/v1/skus", json=payload, headers=SELLER_HEADERS)
    assert resp.status_code == 201, resp.text
    assert resp.json()["cost_price"] == 0


def test_sku_on_moderated_product_triggers_remoderation(client):
    """Adding SKU to MODERATED product re-triggers moderation (b2b-flows.md:257-264)."""
    product_id = _create_product(client, status="MODERATED")
    with patch("src.services.skus._send_moderation_event") as mock_send:
        resp = client.post("/api/v1/skus", json=_sku_payload(product_id), headers=SELLER_HEADERS)
    assert resp.status_code == 201

    db = TestingSession()
    product = db.get(Product, product_id)
    db.close()
    assert product.status == "ON_MODERATION"
    mock_send.assert_called_once()
    _, _, event_arg = mock_send.call_args.args
    assert event_arg == "EDITED"


# ── Дополнительные сценарии ───────────────────────────────────────────────────

def test_unauthorized_returns_401(client):
    resp = client.post("/api/v1/skus", json={"product_id": str(uuid.uuid4())})
    assert resp.status_code == 401


def test_product_not_found_returns_404(client):
    resp = client.post(
        "/api/v1/skus",
        json=_sku_payload(str(uuid.uuid4())),
        headers=SELLER_HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_sku_response_shape(client):
    product_id = _create_product(client)
    with patch("src.services.skus._send_moderation_event"):
        resp = client.post("/api/v1/skus", json=_sku_payload(product_id), headers=SELLER_HEADERS)
    assert resp.status_code == 201
    body = resp.json()
    for field in ("id", "product_id", "name", "price", "cost_price", "discount",
                  "images", "article", "stock_quantity", "active_quantity", "reserved_quantity", "characteristics"):
        assert field in body, f"missing field: {field}"
    assert isinstance(body["images"], list)
    if body["images"]:
        img = body["images"][0]
        assert "id" in img and "url" in img and "ordering" in img
    assert body["active_quantity"] == 0
    assert body["reserved_quantity"] == 0
