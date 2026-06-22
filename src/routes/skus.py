import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth import get_current_seller_id
from src.database import get_db
from src.schemas.product import SKUCreateIn, SKUCreateOut
from src.services.skus import create_sku

router = APIRouter(prefix="/api/v1", tags=["SKUs"])


def _img_id(sku_id: str, ordering: int = 0) -> str:
    """Deterministic UUID for a SKU image (SKU stores one image as a string)."""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f"{sku_id}:img:{ordering}"))


def serialize_sku(sku) -> dict:
    return {
        "id": sku.id,
        "product_id": sku.product_id,
        "name": sku.name,
        "price": sku.price,
        "cost_price": sku.cost_price,
        "discount": sku.discount,
        # SKUImageResponse requires id, url, ordering (openapi b2b:1437-1443)
        "images": [{"id": _img_id(sku.id, 0), "url": sku.image, "ordering": 0}] if sku.image else [],
        "article": sku.article,
        "stock_quantity": sku.stock_quantity,
        "active_quantity": sku.active_quantity,
        "reserved_quantity": sku.reserved_quantity,
        "characteristics": [
            {"name": c.name, "value": c.value} for c in sku.characteristics
        ],
        "created_at": sku.created_at.isoformat() if sku.created_at else None,
        "updated_at": sku.updated_at.isoformat() if sku.updated_at else None,
    }


@router.post("/skus", status_code=201, response_model=SKUCreateOut)
def post_sku(
    body: SKUCreateIn,
    db: Session = Depends(get_db),
    seller_id: uuid.UUID = Depends(get_current_seller_id),
):
    return serialize_sku(create_sku(db, body, seller_id))
