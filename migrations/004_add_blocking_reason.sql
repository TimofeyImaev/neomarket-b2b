-- US-B2B-05: таблицы для причин блокировки и замечаний по полям
CREATE TABLE IF NOT EXISTS blocking_reasons (
    id    VARCHAR(36)  PRIMARY KEY,
    title VARCHAR(500) NOT NULL
);

CREATE TABLE IF NOT EXISTS field_reports (
    id                 VARCHAR(36)  PRIMARY KEY,
    blocking_reason_id VARCHAR(36)  NOT NULL REFERENCES blocking_reasons(id) ON DELETE CASCADE,
    field              VARCHAR(255) NOT NULL,
    message            VARCHAR(500) NOT NULL
);

-- Добавляем FK-ограничение (только если ещё не существует; в Postgres)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_products_blocking_reason'
    ) THEN
        ALTER TABLE products
            ADD CONSTRAINT fk_products_blocking_reason
            FOREIGN KEY (blocking_reason_id) REFERENCES blocking_reasons(id);
    END IF;
END $$;
