# NeoMarket — B2B Seller Cabinet

Команда «алкобаг и точка» (Forge). Модуль: B2B.

Реализовано: US-B2B-01 — создание карточки товара (`POST /api/v1/products`).

## Стек

FastAPI, SQLAlchemy 2, PostgreSQL, PyJWT (HS256), Docker. Тесты — pytest (SQLite in-memory).

## Запуск

```bash
docker compose up
# Swagger UI: http://localhost:8000/docs
```

Миграции `migrations/*.sql` применяются при первом старте Postgres, сидятся две категории.
Секреты — через env (`.env.example`).

## Тесты

```bash
pip install -r requirements-dev.txt
pytest -v
```

Прогоняются в CI (`.github/workflows/ci.yml`). Сценарии канон-flow B2B-1:
create_product_returns_201_with_created_status, seller_id_taken_from_jwt,
missing_images_returns_400, missing_category_returns_400, invalid_category_id_returns_400,
плюс empty_title_returns_400 и unauthorized_returns_401.

## Решения

- Ошибки валидации — `400 {"code": "INVALID_REQUEST", "message": ...}` по канон-flow B2B-1.
  В OpenAPI для POST /products указан 422 — расхождение канона и протокола, кандидат на PR
  в neomarket-protocols.
- `seller_id` берется только из JWT (`sub`), лишние поля тела игнорируются.
- Товар создается в статусе CREATED без SKU и на модерацию не отправляется —
  отправка при первом SKU будет в US-B2B-02.
