"""Eval runner glue — invoked by scripts/run_eval.py."""
from __future__ import annotations

import json
from pathlib import Path

from advisor.eval import fpb, tasks


def run(task_name: str, n: int = 50, out_dir: Path = Path("data/processed")) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    if task_name == "fpb":
        result = fpb.run_fpb(n=n)
        path = out_dir / "eval_fpb.json"
    elif task_name == "custom":
        result = tasks.run_custom()
        path = out_dir / "eval_custom.json"
    else:
        raise ValueError(f"unknown eval task: {task_name}")
    path.write_text(json.dumps(result, indent=2))
    return {"task": task_name, "out": str(path),
            **({"accuracy": result["accuracy"]} if "accuracy" in result else {}),
            **({"summary": result["summary"]} if "summary" in result else {})}
