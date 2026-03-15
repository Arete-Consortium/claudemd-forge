#!/bin/bash
# Restore license_server.db from Litestream S3 replica.
# Usage: fly ssh console -a cmdf-license -C "bash /app/license_server/scripts/restore.sh"
# Or locally: LITESTREAM_* env vars must be set.
set -euo pipefail

DB_PATH="${ANMD_DB_PATH:-/data/license_server.db}"
CONFIG="/app/license_server/litestream.yml"

echo "==> Restoring $DB_PATH from Litestream replica..."

if [ -f "$DB_PATH" ]; then
    BACKUP="${DB_PATH}.bak.$(date +%s)"
    echo "==> Existing database found, backing up to $BACKUP"
    cp "$DB_PATH" "$BACKUP"
fi

litestream restore -config "$CONFIG" "$DB_PATH"

echo "==> Restore complete. Verifying..."
sqlite3 "$DB_PATH" "SELECT COUNT(*) AS license_count FROM licenses;"
echo "==> Done."
