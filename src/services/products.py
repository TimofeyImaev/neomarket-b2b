import uuid

from slugify import slugify
from sqlalchemy.orm import Session

from src.errors import ApiError
from src.models import Category, Product, ProductCharacteristic, ProductImage
from src.schemas.product import ProductCreateIn


def _invalid(message: str) -> ApiError:
    return ApiError(400, "INVALID_REQUEST", message)


def _validate(db: Session, data: ProductCreateIn) -> None:
    if not data.title or not data.title.strip():
        raise _invalid("title is required")
    if len(data.title) > 255:
        raise _invalid("title must be 1-255 characters")
    if not data.description or not data.description.strip():
        raise _invalid("description is required")
    if len(data.description) > 5000:
        raise _invalid("description must be 1-5000 characters")
    if not data.category_id:
        raise _invalid("category_id is required")
    try:
        uuid.UUID(data.category_id)
    except ValueError:
        raise _invalid("category_id must be a valid UUID")
    if not data.images:
        raise _invalid("At least one image is required")
    if any(not img.url or not img.url.strip() for img in data.images):
        raise _invalid("images url is required")
    if db.get(Category, data.category_id) is None:
        raise _invalid("Category not found")


def create_product(db: Session, data: ProductCreateIn, seller_id: uuid.UUID) -> Product:
    _validate(db, data)

    product = Product(
        seller_id=str(seller_id),
        category_id=data.category_id,
        title=data.title.strip(),
        slug=data.slug or f"{slugify(data.title)[:280]}-{uuid.uuid4().hex[:8]}",
        description=data.description.strip(),
    )
    product.images = [ProductImage(url=i.url, ordering=i.ordering) for i in data.images]
    product.characteristics = [
        ProductCharacteristic(name=c.name, value=c.value) for c in data.characteristics
    ]
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def get_product(db: Session, product_id: str, seller_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    # 404 для несуществующего и чужого товара — не раскрываем существование
    if product is None or product.seller_id != str(seller_id):
        raise ApiError(404, "NOT_FOUND", "Product not found")
    return product
