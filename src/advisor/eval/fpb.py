"""Financial PhraseBank sentiment evaluation — replicates a FinGPT-paper benchmark."""
from __future__ import annotations

from advisor.llm.client import chat_text

LABELS = ["negative", "neutral", "positive"]


def _classify(sentence: str) -> str:
    prompt = (
        "Classify the sentiment of this financial sentence as one of: "
        "positive, negative, neutral.\n"
        f"Sentence: {sentence}\n"
        "Answer with one word only."
    )
    out = chat_text([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=4).strip().lower()
    for lab in LABELS:
        if lab in out:
            return lab
    return "neutral"


def run_fpb(n: int = 50, seed: int = 42) -> dict:
    """Returns accuracy + per-class breakdown over n random examples."""
    from datasets import load_dataset

    ds = load_dataset("financial_phrasebank", "sentences_50agree",
                      split="train", trust_remote_code=True)
    ds = ds.shuffle(seed=seed).select(range(min(n, len(ds))))

    correct = 0
    by_class: dict[str, dict] = {lab: {"n": 0, "correct": 0} for lab in LABELS}
    preds = []
    for ex in ds:
        gold = LABELS[ex["label"]]
        pred = _classify(ex["sentence"])
        ok = pred == gold
        correct += int(ok)
        by_class[gold]["n"] += 1
        by_class[gold]["correct"] += int(ok)
        preds.append({"sentence": ex["sentence"], "gold": gold, "pred": pred, "ok": ok})

    return {
        "accuracy": round(correct / len(ds), 4),
        "n": len(ds),
        "by_class": {
            lab: {**v, "accuracy": round(v["correct"] / v["n"], 4) if v["n"] else 0.0}
            for lab, v in by_class.items()
        },
        "predictions": preds,
    }
