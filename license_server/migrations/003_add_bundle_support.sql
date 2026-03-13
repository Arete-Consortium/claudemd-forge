-- Add bundle_id to link multiple licenses from a single purchase
ALTER TABLE licenses ADD COLUMN bundle_id TEXT;
CREATE INDEX IF NOT EXISTS idx_licenses_bundle ON licenses (bundle_id);
