#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_SLUG="${PROJECT_SLUG:-usstock}"
PROJECT_DATA_DIR="${ROOT_DIR}/data/${PROJECT_SLUG}"
BACKUP_DIR="${PROJECT_DATA_DIR}/backups"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "${BACKUP_DIR}"

if [ -f "${PROJECT_DATA_DIR}/${PROJECT_SLUG}_cockpit.db" ]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "${PROJECT_DATA_DIR}/${PROJECT_SLUG}_cockpit.db" ".backup '${BACKUP_DIR}/${PROJECT_SLUG}_cockpit-${STAMP}.db'"
  else
    cp "${PROJECT_DATA_DIR}/${PROJECT_SLUG}_cockpit.db" "${BACKUP_DIR}/${PROJECT_SLUG}_cockpit-${STAMP}.db"
  fi
fi

tar --exclude "${PROJECT_SLUG}/backups" -czf "${BACKUP_DIR}/${PROJECT_SLUG}-data-${STAMP}.tar.gz" -C "${ROOT_DIR}/data" "${PROJECT_SLUG}"

find "${BACKUP_DIR}" -type f -mtime +30 -delete

echo "Backup written to ${BACKUP_DIR}"
