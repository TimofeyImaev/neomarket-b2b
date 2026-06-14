from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
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
    category_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    min_price: Annotated[int | None, Query()] = None,
    max_price: Annotated[int | None, Query()] = None,
    ids: Annotated[str | None, Query(description="Comma-separated product IDs")] = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_key),
):
    id_list = [i.strip() for i in ids.split(",") if i.strip()] if ids else None
    products = get_catalog(
        db,
        ids=id_list,
        category_id=category_id,
        search=search,
        min_price=min_price,
        max_price=max_price,
    )
    items = [_serialize_public(p) for p in products]
    return {"items": items, "total": len(items)}


@router.post("/public/products/batch", status_code=200)
def batch_public_catalog(
    body: Annotated[dict, Body()],
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_key),
):
    product_ids = body.get("product_ids", [])
    products = get_catalog(db, ids=product_ids if product_ids else None)
    items = [_serialize_public(p) for p in products]
    return {"items": items, "total": len(items)}
