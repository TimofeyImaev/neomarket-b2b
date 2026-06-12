# US-B2B-01: создание карточки товара (flows/b2b-flows.md#create-product)

import uuid

from tests.conftest import CATEGORY_ID, auth_headers, valid_payload


def test_create_product_returns_201_with_created_status(client):
    resp = client.post("/api/v1/products", json=valid_payload(), headers=auth_headers())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "CREATED"
    assert body["skus"] == []
    assert body["deleted"] is False
    assert body["title"] == "iPhone 15 Pro Max"
    assert body["category_id"] == CATEGORY_ID
    assert [i["ordering"] for i in body["images"]] == [0, 1]
    assert len(body["characteristics"]) == 2
    assert uuid.UUID(body["id"])


def test_seller_id_taken_from_jwt(client):
    jwt_seller_id = str(uuid.uuid4())
    payload = valid_payload()
    payload["seller_id"] = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/products", json=payload, headers=auth_headers(sub=jwt_seller_id)
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["seller_id"] == jwt_seller_id
    assert resp.json()["seller_id"] != payload["seller_id"]


def test_missing_images_returns_400(client):
    payload = valid_payload()
    del payload["images"]
    resp = client.post("/api/v1/products", json=payload, headers=auth_headers())
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "INVALID_REQUEST"
    assert "image" in resp.json()["message"].lower()


def test_missing_category_returns_400(client):
    payload = valid_payload()
    del payload["category_id"]
    resp = client.post("/api/v1/products", json=payload, headers=auth_headers())
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "INVALID_REQUEST"
    assert "category_id" in resp.json()["message"]


def test_invalid_category_id_returns_400(client):
    payload = valid_payload()
    payload["category_id"] = str(uuid.uuid4())
    resp = client.post("/api/v1/products", json=payload, headers=auth_headers())
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "INVALID_REQUEST"
    assert "category" in resp.json()["message"].lower()

    payload["category_id"] = "not-a-uuid"
    resp = client.post("/api/v1/products", json=payload, headers=auth_headers())
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "INVALID_REQUEST"


def test_empty_title_returns_400(client):
    payload = valid_payload()
    payload["title"] = ""
    resp = client.post("/api/v1/products", json=payload, headers=auth_headers())
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_REQUEST"


def test_unauthorized_returns_401(client):
    resp = client.post("/api/v1/products", json=valid_payload())
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"
