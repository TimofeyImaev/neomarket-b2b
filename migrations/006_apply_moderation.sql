-- US-B2B-09: поля для применения решения модерации

ALTER TABLE blocking_reasons ADD COLUMN IF NOT EXISTS comment TEXT;
ALTER TABLE field_reports ADD COLUMN IF NOT EXISTS sku_id VARCHAR(36);
ALTER TABLE products ADD COLUMN IF NOT EXISTS blocked BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS moderation_event_logs (
    id VARCHAR(36) PRIMARY KEY,
    idempotency_key VARCHAR(36) NOT NULL UNIQUE,
    product_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_moderation_event_logs_idempotency_key
    ON moderation_event_logs(idempotency_key);
