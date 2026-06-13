-- US-B2B-08: таблица для хранения idempotency_key резервирований
CREATE TABLE IF NOT EXISTS reservation_logs (
    id               VARCHAR(36) PRIMARY KEY,
    idempotency_key  VARCHAR(36) NOT NULL UNIQUE,
    operation        VARCHAR(16) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reservation_logs_key ON reservation_logs (idempotency_key);
