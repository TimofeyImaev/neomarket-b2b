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


@router.get("/public/products")
def get_public_catalog(
    request: Request,
    category_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query(alias="q")] = None,
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
    """Returns a plain array of products (b2b/openapi.yaml:835-838)."""
    product_ids = body.get("product_ids", [])
    products = get_catalog(db, ids=product_ids if product_ids else None)
    return [_serialize_public(p) for p in products]


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
    return {
        "id": sku.id,
        "product_id": sku.product_id,
        "name": sku.name,
        "price": sku.price,
        "discount": sku.discount,
        "stock_quantity": sku.active_quantity,   # available = stock - reserved
        "images": [{"url": sku.image}] if sku.image else [],
        "article": sku.article,
        "characteristics": [
            {"name": c.name, "value": c.value} for c in sku.characteristics
        ],
    }
