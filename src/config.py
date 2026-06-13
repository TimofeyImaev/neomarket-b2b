import os

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://neomarket:neomarket@db:5432/b2b",
)
MODERATION_URL = os.getenv("MODERATION_URL", "")
B2B_TO_MOD_KEY = os.getenv("B2B_TO_MOD_KEY", "")
# Ключ, который межсервисные клиенты (B2C, Moderation) передают в X-Service-Key
B2B_SERVICE_KEY = os.getenv("B2B_SERVICE_KEY", "")
