#!/usr/bin/env bash
set -euo pipefail
ROOT="${SHIPRATE_REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT/apps/api"
export PYTHONPATH="${ROOT}/apps/api:${ROOT}"
alembic upgrade head
python scripts/seed_demo_northstar.py
python - <<'PY'
import asyncio
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps/api"))
sys.path.insert(0, str(REPO_ROOT))

from demo.northstar_constants import DEMO_ORG_ID
from sqlalchemy import func, select

from app.db import SessionLocal, set_rls_organization
from app.models import Discrepancy


async def discrepancy_count() -> int:
    async with SessionLocal() as session:
        await set_rls_organization(session, DEMO_ORG_ID)
        return int(
            await session.scalar(
                select(func.count()).select_from(Discrepancy).where(Discrepancy.organization_id == DEMO_ORG_ID)
            )
            or 0
        )


async def main() -> None:
    count = await discrepancy_count()
    if count > 0:
        print(f"bootstrap_try_demo: skip pipeline ({count} discrepancies already loaded)")
        return
    script = REPO_ROOT / "apps/api/scripts/run_northstar_demo.py"
    subprocess.run([sys.executable, str(script), "--skip-seed"], check=True)


asyncio.run(main())
PY
