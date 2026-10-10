#!/usr/bin/env bash
set -euo pipefail
ROOT="${SHIPRATE_REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT/apps/api"
export PYTHONPATH="${ROOT}/apps/api:${ROOT}"
alembic upgrade head
python scripts/seed_demo_northstar.py
python scripts/run_northstar_demo.py --skip-seed
