CREATE TABLE IF NOT EXISTS categories (
    id        VARCHAR(36) PRIMARY KEY,
    name      VARCHAR(255) NOT NULL,
    parent_id VARCHAR(36) REFERENCES categories (id)
);

CREATE TABLE IF NOT EXISTS products (
    id                 VARCHAR(36) PRIMARY KEY,
    seller_id          VARCHAR(36)  NOT NULL,
    category_id        VARCHAR(36)  NOT NULL REFERENCES categories (id),
    title              VARCHAR(255) NOT NULL,
    slug               VARCHAR(300) NOT NULL,
    description        TEXT         NOT NULL,
    status             VARCHAR(20)  NOT NULL DEFAULT 'CREATED',
    deleted            BOOLEAN      NOT NULL DEFAULT FALSE,
    blocking_reason_id VARCHAR(36),
    moderator_comment  TEXT,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_products_seller ON products (seller_id);

CREATE TABLE IF NOT EXISTS product_images (
    id         VARCHAR(36) PRIMARY KEY,
    product_id VARCHAR(36) NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    url        TEXT        NOT NULL,
    ordering   INTEGER     NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS product_characteristics (
    id         VARCHAR(36) PRIMARY KEY,
    product_id VARCHAR(36)  NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    name       VARCHAR(255) NOT NULL,
    value      VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS skus (
    id                VARCHAR(36) PRIMARY KEY,
    product_id        VARCHAR(36)  NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    name              VARCHAR(255) NOT NULL,
    price             INTEGER      NOT NULL,
    discount          INTEGER      NOT NULL DEFAULT 0,
    cost_price        INTEGER,
    stock_quantity    INTEGER      NOT NULL DEFAULT 0,
    reserved_quantity INTEGER      NOT NULL DEFAULT 0,
    article           VARCHAR(100),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);
