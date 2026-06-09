"""Ingest pipeline: corpus files → chunks → embeddings → Chroma."""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from advisor.rag.store import get_or_create_collection

SUPPORTED = {".pdf", ".md", ".txt"}


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
        except Exception as e:
            print(f"  ! failed to parse {path}: {e}")
            return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Character-based chunking with overlap. Sufficient for capstone scope."""
    text = text.strip()
    if not text:
        return []
    out, i = [], 0
    while i < len(text):
        out.append(text[i : i + size])
        i += size - overlap
    return [c for c in out if c.strip()]


def build_index(corpus_dir: Path) -> int:
    """Walk corpus_dir, parse + chunk + add to collection. Returns chunk count."""
    coll = get_or_create_collection()
    files = [p for p in corpus_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED]
    if not files:
        print(f"No supported files under {corpus_dir}. Add PDFs/markdown to corpus/.")
        return 0

    total = 0
    for path in files:
        rel = path.relative_to(corpus_dir)
        print(f"  {rel}")
        text = extract_text(path)
        chunks = chunk_text(text)
        if not chunks:
            continue
        ids = [f"{path.stem}-{i}" for i in range(len(chunks))]
        metas = [{"source": str(rel)} for _ in chunks]
        # Upsert so re-runs don't duplicate
        coll.upsert(ids=ids, documents=chunks, metadatas=metas)
        total += len(chunks)
    return total
