-- US-B2B-02: добавляем image к SKU и таблицу sku_characteristics
ALTER TABLE skus ADD COLUMN IF NOT EXISTS image TEXT;

CREATE TABLE IF NOT EXISTS sku_characteristics (
    id          VARCHAR(36)  PRIMARY KEY,
    sku_id      VARCHAR(36)  NOT NULL REFERENCES skus(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    value       VARCHAR(255) NOT NULL
);
