import uuid

from slugify import slugify
from sqlalchemy import and_, exists, func
from sqlalchemy.orm import Session

from src.errors import ApiError
from src.models import Category, Product, ProductCharacteristic, ProductImage
from src.models.product import SKU
from src.schemas.product import ProductCreateIn


def _invalid(message: str) -> ApiError:
    return ApiError(400, "INVALID_REQUEST", message)


def create_product(db: Session, data: ProductCreateIn, seller_id: uuid.UUID) -> Product:
    if not data.category_id:
        raise _invalid("category_id is required")
    try:
        uuid.UUID(data.category_id)
    except ValueError:
        raise _invalid("category_id must be a valid UUID")
    if not data.title or not data.title.strip():
        raise _invalid("title is required")
    if not data.images:
        raise _invalid("at least one image is required")
    if db.get(Category, data.category_id) is None:
        raise _invalid("category not found or invalid")

    slug = slugify(data.title)
    product = Product(
        seller_id=str(seller_id),
        category_id=data.category_id,
        title=data.title.strip(),
        slug=slug,
        description=data.description or "",
    )
    db.add(product)
    db.flush()

    for img in data.images or []:
        db.add(ProductImage(product_id=product.id, url=img.url, ordering=img.ordering))
    for ch in data.characteristics or []:
        db.add(ProductCharacteristic(product_id=product.id, name=ch.name, value=ch.value))

    db.commit()
    db.refresh(product)
    return product


def get_product(db: Session, product_id: str, seller_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.seller_id != str(seller_id):
        raise ApiError(404, "NOT_FOUND", "Product not found")
    db.refresh(product)
    return product


def get_catalog(
    db: Session,
    ids: list[str] | None = None,
    category_id: str | None = None,
    search: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
) -> list[Product]:
    # Only MODERATED + not deleted + has SKU with available stock
    has_in_stock = exists().where(
        and_(
            SKU.product_id == Product.id,
            (SKU.stock_quantity - SKU.reserved_quantity) > 0,
        )
    )
    query = db.query(Product).filter(
        Product.status == "MODERATED",
        Product.deleted == False,
        has_in_stock,
    )
    if ids:
        query = query.filter(Product.id.in_(ids))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if search:
        query = query.filter(Product.title.ilike(f"%{search}%"))
    if min_price is not None or max_price is not None:
        min_sku_price = (
            db.query(func.min(SKU.price))
            .filter(SKU.product_id == Product.id)
            .correlate(Product)
            .scalar_subquery()
        )
        if min_price is not None:
            query = query.filter(min_sku_price >= min_price)
        if max_price is not None:
            query = query.filter(min_sku_price <= max_price)
    return query.all()
