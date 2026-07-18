#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ ! -f ".env.production" ]; then
  echo "Missing .env.production. Copy .env.production.example and fill it first."
  exit 1
fi

git pull --ff-only
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build backend frontend
docker compose --env-file .env.production -f docker-compose.prod.yml ps
