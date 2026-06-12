import uuid

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import JWT_ALGORITHM, JWT_SECRET
from src.errors import ApiError

_bearer = HTTPBearer(auto_error=False)


def get_current_seller_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID:
    # seller_id берется только из claims (sub), тело запроса не источник
    if credentials is None:
        raise ApiError(401, "UNAUTHORIZED", "Missing Authorization header")
    try:
        claims = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "UNAUTHORIZED", "Token expired")
    except jwt.InvalidTokenError:
        raise ApiError(401, "UNAUTHORIZED", "Invalid token")
    if claims.get("role") != "seller":
        raise ApiError(403, "FORBIDDEN", "Seller role required")
    try:
        return uuid.UUID(str(claims.get("sub")))
    except (ValueError, TypeError):
        raise ApiError(401, "UNAUTHORIZED", "Invalid sub claim")
