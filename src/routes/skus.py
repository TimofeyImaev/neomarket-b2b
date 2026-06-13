import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth import get_current_seller_id
from src.database import get_db
from src.schemas.product import SKUCreateIn, SKUCreateOut
from src.services.skus import create_sku

router = APIRouter(prefix="/api/v1", tags=["SKUs"])


def serialize_sku(sku) -> dict:
    return {
        "id": sku.id,
        "product_id": sku.product_id,
        "name": sku.name,
        "price": sku.price,
        "cost_price": sku.cost_price,
        "discount": sku.discount,
        "image": sku.image,
        "active_quantity": sku.active_quantity,
        "reserved_quantity": sku.reserved_quantity,
        "characteristics": [
            {"name": c.name, "value": c.value} for c in sku.characteristics
        ],
    }


@router.post("/skus", status_code=201, response_model=SKUCreateOut)
def post_sku(
    body: SKUCreateIn,
    db: Session = Depends(get_db),
    seller_id: uuid.UUID = Depends(get_current_seller_id),
):
    return serialize_sku(create_sku(db, body, seller_id))
