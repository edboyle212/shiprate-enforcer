#!/usr/bin/env python3
"""One-shot Northstar file-drop demo: seed, stage CSVs, poll ETL, import, match, compliance."""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from demo.northstar_constants import DEMO_ORG_ID, PARTNER_ID

from app.config import settings
from app.db import SessionLocal, set_rls_organization
from app.services.compliance import run_compliance_for_matches
from app.services.etl_file_drop import (
    poll_etl_drop,
    process_etl_pending_import_jobs,
)
from app.services.matching import run_automatic_matching

FIXTURES = REPO_ROOT / "demo" / "fixtures"


def _stage_drop_files() -> list[Path]:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    staged: list[Path] = []
    mapping = {
        "shipments": FIXTURES / "sample-shipments.csv",
        "invoices": FIXTURES / "sample-invoice.csv",
    }
    base = Path(settings.local_upload_dir) / settings.etl_drop_root / PARTNER_ID / str(DEMO_ORG_ID)
    for folder, src in mapping.items():
        dest_dir = base / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"northstar-demo-{stamp}-{src.name}"
        shutil.copyfile(src, dest)
        staged.append(dest)
    return staged


async def _run_pipeline() -> dict:
    async with SessionLocal() as session:
        await set_rls_organization(session, DEMO_ORG_ID)
        poll = await poll_etl_drop(session, partner_id=PARTNER_ID, organization_id=DEMO_ORG_ID)
        # poll_etl_drop commits; RLS org context is transaction-local — re-apply before each step.
        await set_rls_organization(session, DEMO_ORG_ID)
        mapped = await process_etl_pending_import_jobs(session, organization_id=DEMO_ORG_ID)
        await set_rls_organization(session, DEMO_ORG_ID)
        match = await run_automatic_matching(session, organization_id=DEMO_ORG_ID)
        await set_rls_organization(session, DEMO_ORG_ID)
        compliance = await run_compliance_for_matches(session, organization_id=DEMO_ORG_ID)
        await session.commit()
        return {
            "poll": poll,
            "mapped": mapped,
            "matching": {
                "exact_matches": match.exact_matches,
                "normalized_matches": match.normalized_matches,
                "skipped_already_matched": match.skipped_already_matched,
            },
            "compliance": {
                "checks_created": compliance.checks_created,
                "passed": compliance.passed,
                "discrepancies_created": compliance.discrepancies_created,
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Northstar WMS file-drop demo pipeline")
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip seed_demo_northstar (use when org/partner already exist)",
    )
    args = parser.parse_args()

    if not args.skip_seed:
        seed_script = Path(__file__).resolve().parent / "seed_demo_northstar.py"
        subprocess.run([sys.executable, str(seed_script)], check=True)

    staged = _stage_drop_files()
    print("Staged ETL drop files:")
    for path in staged:
        rel = path.relative_to(Path(settings.local_upload_dir))
        print(f"  {rel}")

    result = asyncio.run(_run_pipeline())
    print("Pipeline result:")
    print(result)
    print()
    print("Open web UI: http://127.0.0.1:43123/discrepancies")
    print(f"Set org in Account or localStorage shiprate_demo_org_id = {DEMO_ORG_ID}")
    print(f"API header: X-Organization-Id: {DEMO_ORG_ID}")


if __name__ == "__main__":
    main()
