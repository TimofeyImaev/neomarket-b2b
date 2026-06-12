from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from src.database import Base, engine
from src.errors import ApiError, api_error_handler, validation_error_handler
from src.routes.products import router as products_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # в проде схему создают migrations/*.sql, create_all идемпотентен
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="NeoMarket B2B Seller Cabinet", version="0.1.0", lifespan=lifespan)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(products_router)


@app.get("/health")
def health():
    return {"status": "ok"}
