"""Load hero customers from data/seed/customers.json into data/profile.db.

Idempotent: `upsert_customer` uses external_id as the natural key, so re-runs
update the same row rather than duplicating.

Usage:
  python scripts/seed_customers.py
  python scripts/seed_customers.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from advisor.domain.data import Customer, Holding, init_db, upsert_customer  # noqa: E402

SEED_JSON = Path("data/seed/customers.json")


def _to_customer(raw: dict) -> Customer:
    holdings = [Holding(**h) for h in raw.get("holdings", [])]
    return Customer(
        id=None, external_id=raw["external_id"], name=raw["name"], age=raw["age"],
        annual_income=raw["annual_income"], dependents=raw.get("dependents", 0),
        risk_answers=raw.get("risk_answers", []),
        primary_goal=raw.get("primary_goal", ""),
        goal_inputs=raw.get("goal_inputs", {}),
        holdings=holdings,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Parse and print, do not write to DB")
    args = ap.parse_args()

    if not SEED_JSON.exists():
        print(f"seed file missing: {SEED_JSON}")
        return 1

    raws = json.loads(SEED_JSON.read_text())
    print(f"Loading {len(raws)} hero customers from {SEED_JSON}")

    if args.dry_run:
        for r in raws:
            print(f"  {r['external_id']:20s}  {r['name']:20s}  {r.get('primary_goal', '-'):20s}"
                  f"  {len(r.get('holdings', []))} holdings")
        return 0

    init_db()
    for raw in raws:
        cid = upsert_customer(_to_customer(raw))
        print(f"  {raw['external_id']:20s}  {raw['name']:20s}  -> id={cid}")

    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
