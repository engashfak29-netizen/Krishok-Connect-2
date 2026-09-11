CREATE INDEX IF NOT EXISTS idx_orders_status_updated ON orders(status,updated_at);
CREATE INDEX IF NOT EXISTS idx_products_active_name ON products(active,name);
