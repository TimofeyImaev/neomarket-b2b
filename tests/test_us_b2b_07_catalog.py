"""
US-B2B-07: Каталог товаров для B2C (service-to-service)
DoD: https://contract.tochka-urfu.tech/quests/contraction-implement-us-b2b-07-catalog-for-b2c
"""
import uuid
from unittest.mock import patch

from tests.conftest import SERVICE_HEADERS, TestingSession, auth_headers, valid_payload
from src.models.product import Product, SKU

CATALOG_URL = "/api/v1/public/products"


def _create_moderated_product_with_stock(client) -> tuple[str, str]:
    seller_headers = auth_headers(str(uuid.uuid4()))
    resp = client.post("/api/v1/products", json=valid_payload(), headers=seller_headers)
    assert resp.status_code == 201
    product_id = resp.json()["id"]

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
            headers=seller_headers,
        )
    assert sku_resp.status_code == 201
    sku_id = sku_resp.json()["id"]

    db = TestingSession()
    product = db.get(Product, product_id)
    product.status = "MODERATED"
    sku = db.get(SKU, sku_id)
    sku.stock_quantity = 10
    db.commit()
    db.close()

    return product_id, sku_id


# ── DoD тесты ────────────────────────────────────────────────────────────────

def test_catalog_returns_moderated_in_stock_products(client):
    product_id, _ = _create_moderated_product_with_stock(client)

    resp = client.get(CATALOG_URL, headers=SERVICE_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    ids = [p["id"] for p in body["items"]]
    assert product_id in ids


def test_catalog_excludes_hard_blocked(client):
    product_id, _ = _create_moderated_product_with_stock(client)

    db = TestingSession()
    product = db.get(Product, product_id)
    product.status = "HARD_BLOCKED"
    db.commit()
    db.close()

    resp = client.get(CATALOG_URL, headers=SERVICE_HEADERS)
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]
    assert product_id not in ids


def test_catalog_missing_service_key_returns_401(client):
    resp = client.get(CATALOG_URL)
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_catalog_response_has_no_cost_price(client):
    product_id, _ = _create_moderated_product_with_stock(client)

    resp = client.get(CATALOG_URL, headers=SERVICE_HEADERS)
    assert resp.status_code == 200
    items = resp.json()["items"]
    target = next(p for p in items if p["id"] == product_id)
    # Public schema: no seller-private fields
    assert "cost_price" not in target
    assert "reserved_quantity" not in target
    assert "seller_id" not in target
    # Required public fields present
    for field in ("id", "title", "slug", "status", "category_id", "created_at"):
        assert field in target, f"missing field: {field}"


def test_batch_ids_returns_visible_subset(client):
    visible_id, _ = _create_moderated_product_with_stock(client)

    seller_headers = auth_headers(str(uuid.uuid4()))
    resp = client.post("/api/v1/products", json=valid_payload(), headers=seller_headers)
    hidden_id = resp.json()["id"]

    random_id = str(uuid.uuid4())

    resp = client.get(f"{CATALOG_URL}?ids={visible_id},{hidden_id},{random_id}", headers=SERVICE_HEADERS)
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]
    assert visible_id in ids
    assert hidden_id not in ids
    assert random_id not in ids


# ── Дополнительные сценарии ───────────────────────────────────────────────────

def test_catalog_excludes_out_of_stock(client):
    product_id, sku_id = _create_moderated_product_with_stock(client)

    db = TestingSession()
    sku = db.get(SKU, sku_id)
    sku.stock_quantity = 0
    db.commit()
    db.close()

    resp = client.get(CATALOG_URL, headers=SERVICE_HEADERS)
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]
    assert product_id not in ids


def test_catalog_excludes_deleted(client):
    product_id, _ = _create_moderated_product_with_stock(client)

    db = TestingSession()
    product = db.get(Product, product_id)
    product.deleted = True
    db.commit()
    db.close()

    resp = client.get(CATALOG_URL, headers=SERVICE_HEADERS)
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]
    assert product_id not in ids
