#!/usr/bin/env python3
"""CLI eval runner.

Examples:
  python scripts/run_eval.py --task fpb --n 50
  python scripts/run_eval.py --task custom
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from advisor.eval.runner import run  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=["fpb", "custom"])
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()
    out = run(args.task, n=args.n)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
