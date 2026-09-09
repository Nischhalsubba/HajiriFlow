#!/usr/bin/env bash
set -euo pipefail

: "${HAJIRIFLOW_BACKUP_DATABASE_URL:?Set HAJIRIFLOW_BACKUP_DATABASE_URL to a PostgreSQL URL.}"
: "${HAJIRIFLOW_BACKUP_PATH:?Set HAJIRIFLOW_BACKUP_PATH to the destination .dump file.}"

case "$HAJIRIFLOW_BACKUP_PATH" in
  *.dump) ;;
  *) echo "Backup path must end in .dump" >&2; exit 2 ;;
esac

umask 077
backup_dir=$(dirname -- "$HAJIRIFLOW_BACKUP_PATH")
backup_name=$(basename -- "$HAJIRIFLOW_BACKUP_PATH")
mkdir -p -- "$backup_dir"
temporary="$backup_dir/.${backup_name}.tmp.$$"
checksum="$HAJIRIFLOW_BACKUP_PATH.sha256"
trap 'rm -f -- "$temporary"' EXIT

pg_dump \
  --dbname="$HAJIRIFLOW_BACKUP_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  > "$temporary"

test -s "$temporary"
mv -- "$temporary" "$HAJIRIFLOW_BACKUP_PATH"
(
  cd -- "$backup_dir"
  sha256sum -- "$backup_name" > "$(basename -- "$checksum")"
)
chmod 600 -- "$HAJIRIFLOW_BACKUP_PATH" "$checksum"
trap - EXIT
printf 'HajiriFlow PostgreSQL backup completed: %s\n' "$HAJIRIFLOW_BACKUP_PATH"
