import os
import time
import uuid

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["B2B_SERVICE_KEY"] = "test-service-key"

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base, get_db
from src.main import app
from src.models import Category

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db

CATEGORY_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
SERVICE_HEADERS = {"X-Service-Key": "test-service-key"}


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    db.add(Category(id=CATEGORY_ID, name="Смартфоны"))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def make_token(sub: str | None = None, role: str = "seller") -> str:
    now = int(time.time())
    claims = {
        "sub": sub or str(uuid.uuid4()),
        "role": role,
        "iat": now,
        "exp": now + 3600,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, "test-secret", algorithm="HS256")


def auth_headers(sub: str | None = None) -> dict:
    return {"Authorization": f"Bearer {make_token(sub)}"}


def valid_payload() -> dict:
    return {
        "title": "iPhone 15 Pro Max",
        "description": "Флагманский смартфон Apple 2024 года с чипом A17 Pro",
        "category_id": CATEGORY_ID,
        "images": [
            {"url": "/s3/iphone15-front.jpg", "ordering": 0},
            {"url": "/s3/iphone15-back.jpg", "ordering": 1},
        ],
        "characteristics": [
            {"name": "Бренд", "value": "Apple"},
            {"name": "Страна-производитель", "value": "Китай"},
        ],
    }
