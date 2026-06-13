"""
US-B2B-08: Резервирование и снятие резерва SKU
DoD: https://contract.tochka-urfu.tech/quests/contraction-implement-us-b2b-08-reserve-sku
"""
import uuid
from unittest.mock import patch

from tests.conftest import SERVICE_HEADERS, TestingSession, auth_headers, valid_payload
from src.models.product import Product, SKU


def _create_sku_with_stock(client, stock: int = 10) -> tuple[str, str]:
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
    sku = db.get(SKU, sku_id)
    sku.stock_quantity = stock
    db.commit()
    db.close()

    return product_id, sku_id


def _reserve_payload(sku_id: str, quantity: int = 3, key: str | None = None) -> dict:
    return {
        "idempotency_key": key or str(uuid.uuid4()),
        "items": [{"sku_id": sku_id, "quantity": quantity}],
    }


# ── DoD тесты ────────────────────────────────────────────────────────────────

def test_reserve_all_skus_succeeds(client):
    _, sku_id = _create_sku_with_stock(client, stock=10)

    resp = client.post("/api/v1/reserve", json=_reserve_payload(sku_id, 3), headers=SERVICE_HEADERS)
    assert resp.status_code == 200

    db = TestingSession()
    sku = db.get(SKU, sku_id)
    db.close()
    assert sku.reserved_quantity == 3
    assert sku.active_quantity == 7


def test_partial_insufficient_stock_returns_409_all_rollback(client):
    _, sku_id_1 = _create_sku_with_stock(client, stock=10)
    _, sku_id_2 = _create_sku_with_stock(client, stock=2)

    resp = client.post(
        "/api/v1/reserve",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "items": [
                {"sku_id": sku_id_1, "quantity": 5},
                {"sku_id": sku_id_2, "quantity": 5},  # недостаточно
            ],
        },
        headers=SERVICE_HEADERS,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "INSUFFICIENT_STOCK"

    db = TestingSession()
    sku1 = db.get(SKU, sku_id_1)
    sku2 = db.get(SKU, sku_id_2)
    db.close()
    assert sku1.reserved_quantity == 0
    assert sku2.reserved_quantity == 0


def test_idempotent_reserve_returns_200_without_double_deduction(client):
    _, sku_id = _create_sku_with_stock(client, stock=10)
    key = str(uuid.uuid4())

    resp1 = client.post("/api/v1/reserve", json=_reserve_payload(sku_id, 3, key), headers=SERVICE_HEADERS)
    assert resp1.status_code == 200

    resp2 = client.post("/api/v1/reserve", json=_reserve_payload(sku_id, 3, key), headers=SERVICE_HEADERS)
    assert resp2.status_code == 200

    db = TestingSession()
    sku = db.get(SKU, sku_id)
    db.close()
    assert sku.reserved_quantity == 3  # не 6


def test_sku_out_of_stock_event_emitted(client):
    _, sku_id = _create_sku_with_stock(client, stock=3)

    with patch("src.services.reserve._send_out_of_stock_event") as mock_event:
        resp = client.post("/api/v1/reserve", json=_reserve_payload(sku_id, 3), headers=SERVICE_HEADERS)
    assert resp.status_code == 200
    mock_event.assert_called_once_with(sku_id)


def test_unreserve_restores_quantities(client):
    _, sku_id = _create_sku_with_stock(client, stock=10)

    client.post("/api/v1/reserve", json=_reserve_payload(sku_id, 5), headers=SERVICE_HEADERS)

    resp = client.post(
        "/api/v1/unreserve",
        json={"idempotency_key": str(uuid.uuid4()), "items": [{"sku_id": sku_id, "quantity": 3}]},
        headers=SERVICE_HEADERS,
    )
    assert resp.status_code == 200

    db = TestingSession()
    sku = db.get(SKU, sku_id)
    db.close()
    assert sku.reserved_quantity == 2
    assert sku.active_quantity == 8


# ── Дополнительные сценарии ───────────────────────────────────────────────────

def test_reserve_missing_service_key_returns_401(client):
    resp = client.post("/api/v1/reserve", json={"idempotency_key": str(uuid.uuid4()), "items": []})
    assert resp.status_code == 401


def test_reserve_nonexistent_sku_returns_404(client):
    resp = client.post(
        "/api/v1/reserve",
        json=_reserve_payload(str(uuid.uuid4()), 1),
        headers=SERVICE_HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_out_of_stock_event_not_emitted_when_stock_remains(client):
    _, sku_id = _create_sku_with_stock(client, stock=10)

    with patch("src.services.reserve._send_out_of_stock_event") as mock_event:
        client.post("/api/v1/reserve", json=_reserve_payload(sku_id, 3), headers=SERVICE_HEADERS)
    mock_event.assert_not_called()
