#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() {
  trap - INT TERM EXIT
  kill 0
}

trap cleanup INT TERM EXIT

echo "Starting backend on http://localhost:8000"
(
  cd "$ROOT_DIR/backend"
  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
) &

echo "Starting experimental frontend"
(
  cd "$ROOT_DIR/frontend"
  VITE_VIEWER_WS_URL="${VITE_VIEWER_WS_URL:-ws://localhost:8000/ws/viewer}" \
    npm run dev
) &

wait
