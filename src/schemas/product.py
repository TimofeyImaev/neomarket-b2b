from pydantic import BaseModel, ConfigDict, Field


class ImageIn(BaseModel):
    url: str
    ordering: int = 0


class CharacteristicIn(BaseModel):
    name: str
    value: str


class SKUCreateIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product_id: str | None = None
    name: str | None = None
    price: int | None = None
    cost_price: int | None = None
    discount: int = 0
    image: str | None = None
    characteristics: list[CharacteristicIn] = Field(default_factory=list)


class SKUCharacteristicOut(BaseModel):
    name: str
    value: str


class SKUCreateOut(BaseModel):
    id: str
    product_id: str
    name: str
    price: int
    cost_price: int
    discount: int
    image: str
    active_quantity: int
    reserved_quantity: int
    characteristics: list[SKUCharacteristicOut]


class ProductCreateIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    description: str | None = None
    category_id: str | None = None
    slug: str | None = None
    images: list[ImageIn] | None = None
    characteristics: list[CharacteristicIn] = Field(default_factory=list)


class ImageOut(BaseModel):
    id: str
    url: str
    ordering: int


class CharacteristicOut(BaseModel):
    id: str
    name: str
    value: str


class SKUOut(BaseModel):
    id: str
    product_id: str
    name: str
    price: int
    discount: int
    cost_price: int | None
    stock_quantity: int
    active_quantity: int
    reserved_quantity: int
    article: str | None
    created_at: str
    updated_at: str


class ProductOut(BaseModel):
    id: str
    seller_id: str
    category_id: str
    title: str
    slug: str
    description: str
    status: str
    deleted: bool
    blocking_reason_id: str | None
    moderator_comment: str | None
    images: list[ImageOut]
    characteristics: list[CharacteristicOut]
    skus: list[SKUOut]
    created_at: str
    updated_at: str


# ── US-B2B-05: GET /api/v1/products/{id} ─────────────────────────────────────

class FieldReportOut(BaseModel):
    field: str
    message: str


class BlockingReasonOut(BaseModel):
    title: str
    field_reports: list[FieldReportOut]


class SKUDetailOut(BaseModel):
    id: str
    product_id: str
    name: str
    price: int
    cost_price: int | None
    discount: int
    image: str | None
    stock_quantity: int
    reserved_quantity: int
    active_quantity: int
    article: str | None
    characteristics: list[SKUCharacteristicOut]
    created_at: str
    updated_at: str


class ProductDetailOut(BaseModel):
    id: str
    seller_id: str
    category_id: str
    title: str
    slug: str
    description: str
    status: str
    deleted: bool
    blocking_reason: BlockingReasonOut | None
    moderator_comment: str | None
    images: list[ImageOut]
    characteristics: list[CharacteristicOut]
    skus: list[SKUDetailOut]
    created_at: str
    updated_at: str
