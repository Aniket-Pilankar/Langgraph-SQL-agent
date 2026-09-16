-- No FK constraints: the source dataset contains orphan rows and duplicate review_ids.

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS sellers;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id        TEXT,
    customer_unique_id TEXT,
    zip_code           TEXT,
    city               TEXT,
    state              TEXT
);

CREATE TABLE orders (
    order_id            TEXT,
    customer_id         TEXT,
    status              TEXT,
    purchase_timestamp  TIMESTAMPTZ,
    approved_at         TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    estimated_delivery  TIMESTAMPTZ
);

CREATE TABLE order_items (
    order_id            TEXT,
    order_item_id       INTEGER,
    product_id          TEXT,
    seller_id           TEXT,
    shipping_limit_date TIMESTAMPTZ,
    price               NUMERIC,
    freight_value       NUMERIC
);

CREATE TABLE products (
    product_id         TEXT,
    category_name      TEXT,
    name_length        INTEGER,
    description_length INTEGER,
    photos_qty         INTEGER,
    weight_g           NUMERIC
);

CREATE TABLE sellers (
    seller_id TEXT,
    zip_code  TEXT,
    city      TEXT,
    state     TEXT
);

CREATE TABLE payments (
    order_id           TEXT,
    payment_sequential INTEGER,
    payment_type       TEXT,
    installments       INTEGER,
    payment_value      NUMERIC
);

CREATE TABLE reviews (
    review_id            TEXT,
    order_id             TEXT,
    review_score         INTEGER,
    comment_title        TEXT,
    comment_message      TEXT,
    review_creation_date TIMESTAMPTZ
);

CREATE INDEX idx_orders_customer_id    ON orders(customer_id);
CREATE INDEX idx_order_items_order_id  ON order_items(order_id);
CREATE INDEX idx_order_items_product   ON order_items(product_id);
CREATE INDEX idx_order_items_seller    ON order_items(seller_id);
CREATE INDEX idx_payments_order_id     ON payments(order_id);
CREATE INDEX idx_reviews_order_id      ON reviews(order_id);
