import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth import get_current_seller_id
from src.database import get_db
from src.schemas.product import ProductCreateIn, ProductOut
from src.services.products import create_product

router = APIRouter(prefix="/api/v1", tags=["Products"])


def serialize_product(product) -> dict:
    return {
        "id": product.id,
        "seller_id": product.seller_id,
        "category_id": product.category_id,
        "title": product.title,
        "slug": product.slug,
        "description": product.description,
        "status": product.status,
        "deleted": product.deleted,
        "blocking_reason_id": product.blocking_reason_id,
        "moderator_comment": product.moderator_comment,
        "images": [
            {"id": i.id, "url": i.url, "ordering": i.ordering} for i in product.images
        ],
        "characteristics": [
            {"id": c.id, "name": c.name, "value": c.value}
            for c in product.characteristics
        ],
        "skus": [
            {
                "id": s.id,
                "product_id": s.product_id,
                "name": s.name,
                "price": s.price,
                "discount": s.discount,
                "cost_price": s.cost_price,
                "stock_quantity": s.stock_quantity,
                "active_quantity": s.active_quantity,
                "reserved_quantity": s.reserved_quantity,
                "article": s.article,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in product.skus
        ],
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


@router.post("/products", status_code=201, response_model=ProductOut)
def post_product(
    body: ProductCreateIn,
    db: Session = Depends(get_db),
    seller_id: uuid.UUID = Depends(get_current_seller_id),
):
    return serialize_product(create_product(db, body, seller_id))
