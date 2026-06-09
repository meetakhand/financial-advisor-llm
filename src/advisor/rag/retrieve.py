"""Hybrid retriever: BM25 + dense (Chroma) fused via reciprocal-rank fusion."""
from __future__ import annotations

from rank_bm25 import BM25Okapi

from advisor.rag.store import get_or_create_collection


class HybridRetriever:
    def __init__(self):
        # Use get_or_create so a fresh install (no index built yet) doesn't crash;
        # the retriever will simply return no snippets until the index is populated.
        self.coll = get_or_create_collection()
        docs = self.coll.get()
        self.ids: list[str] = docs.get("ids", []) or []
        self.texts: list[str] = docs.get("documents", []) or []
        self.metas: list[dict] = docs.get("metadatas", []) or []
        self._id_to_pos = {i: pos for pos, i in enumerate(self.ids)}
        if self.texts:
            self.bm25 = BM25Okapi([t.lower().split() for t in self.texts])
        else:
            self.bm25 = None

    def search(self, query: str, k: int = 6) -> list[dict]:
        if not self.texts:
            return []
        q_tokens = query.lower().split()
        # BM25 top
        bm25_scores = self.bm25.get_scores(q_tokens)
        bm25_top_pos = sorted(range(len(self.texts)), key=lambda i: -bm25_scores[i])[: k * 2]
        bm25_top_ids = [self.ids[i] for i in bm25_top_pos]
        # Dense top
        dense = self.coll.query(query_texts=[query], n_results=min(k * 2, len(self.texts)))
        dense_ids = (dense.get("ids") or [[]])[0]
        # RRF fusion
        rrf: dict[str, float] = {}
        for rank, did in enumerate(bm25_top_ids):
            rrf[did] = rrf.get(did, 0) + 1 / (60 + rank)
        for rank, did in enumerate(dense_ids):
            rrf[did] = rrf.get(did, 0) + 1 / (60 + rank)
        top = sorted(rrf.items(), key=lambda x: -x[1])[:k]
        out = []
        for did, score in top:
            pos = self._id_to_pos.get(did)
            if pos is None:
                continue
            out.append({
                "id": did,
                "text": self.texts[pos],
                "source": (self.metas[pos] or {}).get("source", "unknown"),
                "score": round(score, 4),
            })
        return out


def format_snippets(snippets: list[dict], max_chars: int = 2400) -> str:
    blocks = []
    used = 0
    for s in snippets:
        block = f"[Source: {s['source']}]\n{s['text']}"
        if used + len(block) > max_chars:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)
