#!/usr/bin/env bash
# One command: seed Northstar demo + file-drop ingest + match + compliance.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/api"
export PYTHONPATH="${ROOT}/apps/api:${ROOT}"
export ALLOW_DEV_TENANT_HEADER="${ALLOW_DEV_TENANT_HEADER:-1}"
exec python3 scripts/run_northstar_demo.py "$@"
