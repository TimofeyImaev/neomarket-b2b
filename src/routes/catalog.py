from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.auth import verify_service_key
from src.database import get_db
from src.schemas.product import CatalogResponse
from src.services.products import get_catalog

router = APIRouter(prefix="/api/v1", tags=["Catalog"])


def _serialize_sku(s) -> dict:
    return {
        "id": s.id,
        "product_id": s.product_id,
        "name": s.name,
        "price": s.price,
        "discount": s.discount,
        "image": s.image,
        "stock_quantity": s.stock_quantity,
        "active_quantity": s.active_quantity,
        "article": s.article,
        "characteristics": [
            {"name": c.name, "value": c.value} for c in s.characteristics
        ],
    }


def _serialize_product(p) -> dict:
    return {
        "id": p.id,
        "seller_id": p.seller_id,
        "category_id": p.category_id,
        "title": p.title,
        "slug": p.slug,
        "description": p.description,
        "status": p.status,
        "images": [
            {"id": i.id, "url": i.url, "ordering": i.ordering} for i in p.images
        ],
        "characteristics": [
            {"id": c.id, "name": c.name, "value": c.value}
            for c in p.characteristics
        ],
        "skus": [_serialize_sku(s) for s in p.skus],
    }


@router.get("/products", response_model=CatalogResponse)
def get_catalog_endpoint(
    ids: Annotated[str | None, Query(description="Comma-separated product IDs")] = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_key),
):
    id_list = [i.strip() for i in ids.split(",") if i.strip()] if ids else None
    products = get_catalog(db, ids=id_list)
    items = [_serialize_product(p) for p in products]
    return {"items": items, "total": len(items)}
