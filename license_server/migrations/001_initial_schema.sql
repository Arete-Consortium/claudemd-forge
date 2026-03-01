-- License server initial schema.

CREATE TABLE IF NOT EXISTS licenses (
    id TEXT PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    license_key_masked TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'pro',
    email TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_licenses_key_hash ON licenses (key_hash);
CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses (email);

CREATE TABLE IF NOT EXISTS machine_activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_id TEXT NOT NULL REFERENCES licenses(id),
    machine_id TEXT NOT NULL,
    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(license_id, machine_id)
);

CREATE INDEX IF NOT EXISTS idx_machine_activations_license ON machine_activations (license_id);

CREATE TABLE IF NOT EXISTS validation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL,
    machine_id TEXT,
    result TEXT NOT NULL,
    ip_address TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_validation_log_created ON validation_log (created_at);
