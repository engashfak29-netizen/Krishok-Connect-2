#!/usr/bin/env bash
set -euo pipefail
# Run from backend directory on the production host.
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$OUT_DIR"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
DB_SERVICE="${DB_SERVICE:-db}"
DB_NAME="${POSTGRES_DB:-krishok_connect}"
DB_USER="${POSTGRES_USER:-krishok}"
FILE="$OUT_DIR/krishok_connect_${STAMP}.dump"
docker compose -f docker-compose.production.yml exec -T "$DB_SERVICE" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$FILE"
sha256sum "$FILE" > "$FILE.sha256"
find "$OUT_DIR" -type f -name '*.dump' -mtime +14 -delete
find "$OUT_DIR" -type f -name '*.sha256' -mtime +14 -delete
echo "Backup created: $FILE"
