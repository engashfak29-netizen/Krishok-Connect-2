#!/usr/bin/env bash
set -euo pipefail
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
FILE="${1:?Usage: ./restore.sh backups/file.dump}"
DB_SERVICE="${DB_SERVICE:-db}"; DB_NAME="${POSTGRES_DB:-krishok_connect}"; DB_USER="${POSTGRES_USER:-krishok}"
if [ -f "$FILE.sha256" ]; then sha256sum -c "$FILE.sha256"; fi
cat "$FILE" | docker compose -f docker-compose.production.yml exec -T "$DB_SERVICE" pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner
 echo "Restore completed from: $FILE"
