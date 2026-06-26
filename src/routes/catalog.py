from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy.orm import Session

from src.auth import verify_service_key
from src.database import get_db
from src.services.products import get_catalog

router = APIRouter(prefix="/api/v1", tags=["Public Catalog"])


def _cover_image(product) -> str | None:
    images = sorted(product.images, key=lambda i: i.ordering)
    return images[0].url if images else None


def _min_price(product) -> int | None:
    prices = [s.price for s in product.skus if s.price]
    return min(prices) if prices else None


def _serialize_public(p) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "slug": p.slug,
        "status": p.status,
        "category_id": p.category_id,
        "min_price": _min_price(p),
        "cover_image": _cover_image(p),
        "created_at": p.created_at.isoformat(),
    }


def _serialize_sku_public(s) -> dict:
    """SKUPublicResponse — without cost_price and reserved_quantity."""
    import uuid as _uuid
    img_id = str(_uuid.uuid5(_uuid.NAMESPACE_OID, f"{s.id}:img:0"))
    return {
        "id": s.id,
        "name": s.name,
        "price": s.price,
        "discount": s.discount,
        "article": s.article,
        "stock_quantity": s.stock_quantity,
        "active_quantity": s.active_quantity,
        "images": [{"id": img_id, "url": s.image, "ordering": 0}] if s.image else [],
        "characteristics": [{"id": c.id, "name": c.name, "value": c.value} for c in s.characteristics],
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _serialize_full_public(p) -> dict:
    """ProductPublicResponse — full format for batch endpoint (openapi b2b:1342-1353)."""
    return {
        "id": p.id,
        "seller_id": p.seller_id,
        "category_id": p.category_id,
        "title": p.title,
        "slug": p.slug,
        "description": p.description,
        "status": p.status,
        "images": [
            {"id": img.id, "url": img.url, "ordering": img.ordering}
            for img in sorted(p.images, key=lambda i: i.ordering)
        ],
        "characteristics": [
            {"id": c.id, "name": c.name, "value": c.value} for c in p.characteristics
        ],
        "skus": [_serialize_sku_public(s) for s in p.skus],
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/public/products")
def get_public_catalog(
    request: Request,
    category_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    sort: Annotated[str | None, Query()] = None,
    min_price: Annotated[int | None, Query()] = None,
    max_price: Annotated[int | None, Query()] = None,
    ids: Annotated[str | None, Query(description="Comma-separated product IDs")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_key),
):
    # Parse deepObject filter params: filters[key]=value
    filter_kwargs: dict = {}
    for raw_key, value in request.query_params.multi_items():
        if raw_key.startswith("filters[") and raw_key.endswith("]"):
            key = raw_key[len("filters["):-1]
            if key == "category_id":
                filter_kwargs["category_id"] = value
            # other keys are silently accepted but not currently filtered on

    eff_category = filter_kwargs.get("category_id", category_id)
    id_list = [i.strip() for i in ids.split(",") if i.strip()] if ids else None
    products = get_catalog(
        db,
        ids=id_list,
        category_id=eff_category,
        search=search,
        min_price=min_price,
        max_price=max_price,
    )
    items = [_serialize_public(p) for p in products]
    total_count = len(items)
    page_items = items[offset:offset + limit]
    return {"items": page_items, "total_count": total_count, "limit": limit, "offset": offset}


@router.post("/public/products/batch", status_code=200)
def batch_public_catalog(
    body: Annotated[dict, Body()],
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_key),
):
    """Returns a plain array of ProductPublicResponse (b2b/openapi.yaml:835-838)."""
    product_ids = body.get("product_ids", [])
    products = get_catalog(db, ids=product_ids if product_ids else None)
    return [_serialize_full_public(p) for p in products]


@router.get("/public/skus/{sku_id}")
def get_public_sku(
    sku_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_key),
):
    """Single SKU lookup for B2C cart/checkout enrichment."""
    from src.models.product import SKU
    from src.errors import ApiError

    sku = db.get(SKU, sku_id)
    if sku is None:
        raise ApiError(404, "NOT_FOUND", "SKU not found")
    import uuid as _uuid
    _img = str(_uuid.uuid5(_uuid.NAMESPACE_OID, f"{sku.id}:img:0"))
    return {
        "id": sku.id,
        "product_id": sku.product_id,
        "name": sku.name,
        "price": sku.price,
        "discount": sku.discount,
        "stock_quantity": sku.stock_quantity,    # складской остаток
        "active_quantity": sku.active_quantity,  # доступный = stock - reserved
        "images": [{"id": _img, "url": sku.image, "ordering": 0}] if sku.image else [],
        "article": sku.article,
        "characteristics": [
            {"id": c.id, "name": c.name, "value": c.value} for c in sku.characteristics
        ],
    }
