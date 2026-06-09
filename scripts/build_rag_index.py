#!/usr/bin/env python3
"""Walk corpus/ and build the persistent Chroma index."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advisor.rag.ingest import build_index  # noqa: E402

if __name__ == "__main__":
    corpus = ROOT / "corpus"
    print(f"Building index from {corpus}…")
    n = build_index(corpus)
    print(f"Done. {n} chunks indexed.")
