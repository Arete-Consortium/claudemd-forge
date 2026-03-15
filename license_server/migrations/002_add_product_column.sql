-- Add product column for multi-product license support.

ALTER TABLE licenses ADD COLUMN product TEXT NOT NULL DEFAULT 'anchormd';

CREATE INDEX IF NOT EXISTS idx_licenses_product ON licenses (product);
CREATE INDEX IF NOT EXISTS idx_licenses_product_email ON licenses (product, email);
