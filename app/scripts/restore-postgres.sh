#!/usr/bin/env bash
set -euo pipefail

: "${HAJIRIFLOW_RESTORE_TARGET_URL:?Set HAJIRIFLOW_RESTORE_TARGET_URL to the target PostgreSQL URL.}"
: "${HAJIRIFLOW_RESTORE_BACKUP_PATH:?Set HAJIRIFLOW_RESTORE_BACKUP_PATH to a .dump backup.}"
: "${HAJIRIFLOW_RESTORE_CONFIRM:?Set HAJIRIFLOW_RESTORE_CONFIRM to I_UNDERSTAND_THIS_REPLACES_THE_TARGET.}"

if [ "$HAJIRIFLOW_RESTORE_CONFIRM" != "I_UNDERSTAND_THIS_REPLACES_THE_TARGET" ]; then
  echo "Restore confirmation phrase is invalid." >&2
  exit 2
fi
if [ ! -s "$HAJIRIFLOW_RESTORE_BACKUP_PATH" ]; then
  echo "Backup file does not exist or is empty." >&2
  exit 2
fi
case "${HAJIRIFLOW_ENVIRONMENT:-development}" in
  production)
    if [ "${HAJIRIFLOW_ALLOW_PRODUCTION_RESTORE:-no}" != "yes" ]; then
      echo "Production restore is blocked unless HAJIRIFLOW_ALLOW_PRODUCTION_RESTORE=yes." >&2
      exit 2
    fi
    ;;
esac

checksum="$HAJIRIFLOW_RESTORE_BACKUP_PATH.sha256"
if [ -f "$checksum" ]; then
  (
    cd -- "$(dirname -- "$HAJIRIFLOW_RESTORE_BACKUP_PATH")"
    sha256sum --check -- "$(basename -- "$checksum")"
  )
fi

pg_restore \
  --dbname="$HAJIRIFLOW_RESTORE_TARGET_URL" \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  < "$HAJIRIFLOW_RESTORE_BACKUP_PATH"

printf 'HajiriFlow PostgreSQL restore completed into the explicitly configured target.\n'
