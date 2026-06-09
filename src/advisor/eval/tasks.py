"""Custom advisor-task evaluation set + LLM-as-judge scoring."""
from __future__ import annotations

import json

from advisor.agent.react import run as agent_run
from advisor.llm.client import chat_text
from advisor.rag.retrieve import HybridRetriever

PILLAR_CONVERSATIONAL = "conversational"
PILLAR_INVESTMENT = "investment"
PILLAR_GOAL = "goal"

TASKS: list[dict] = [
    {"pillar": PILLAR_CONVERSATIONAL, "id": "c1",
     "prompt": "What is dollar-cost averaging and what are its tradeoffs?",
     "rubric": "Defines DCA, lists pros (discipline, lower entry-timing risk) and cons (lower expected return in rising markets); does not prescribe a buy."},
    {"pillar": PILLAR_CONVERSATIONAL, "id": "c2",
     "prompt": "Explain the difference between a Roth IRA and a Traditional IRA.",
     "rubric": "Distinguishes pre-tax vs post-tax, RMD differences, income limits; cites IRS-style source if available."},
    {"pillar": PILLAR_CONVERSATIONAL, "id": "c3",
     "prompt": "What is an ETF expense ratio and why does it matter?",
     "rubric": "Defines expense ratio, explains compounding drag on returns; gives realistic ranges."},
    {"pillar": PILLAR_INVESTMENT, "id": "i1",
     "prompt": "Give me a brief profile of AAPL — sector, recent quote, and any notable news sentiment.",
     "rubric": "Calls quote + overview + news_sentiment tools; cites Alpha Vantage; balanced, no buy directive."},
    {"pillar": PILLAR_INVESTMENT, "id": "i2",
     "prompt": "Compare MSFT and GOOGL for a moderate-risk investor.",
     "rubric": "Tool-calls fundamentals for both, highlights differences (sector exposure, valuation, beta), refuses to pick a winner."},
    {"pillar": PILLAR_INVESTMENT, "id": "i3",
     "prompt": "How are US sectors performing today?",
     "rubric": "Calls get_sector_performance, summarizes leaders/laggards, no forecast."},
    {"pillar": PILLAR_GOAL, "id": "g1",
     "prompt": "I'm 30, want to retire at 60 with $2M, currently have $50k saved and contribute $1500/month. Am I on track at a 7% return?",
     "rubric": "Calls retirement_projection, reports projected FV vs target, identifies gap if any."},
    {"pillar": PILLAR_GOAL, "id": "g2",
     "prompt": "How much should I save monthly to reach $500k in 20 years assuming 6% returns?",
     "rubric": "Calls savings_goal, returns specific monthly figure with assumptions stated."},
    {"pillar": PILLAR_GOAL, "id": "g3",
     "prompt": "I'm 35, moderate risk — what's a reasonable stocks/bonds split?",
     "rubric": "Calls asset_allocation, returns 3-bucket split with rationale; calls out it's a starting point not advice."},
    {"pillar": PILLAR_GOAL, "id": "g4",
     "prompt": "I have $20k credit card debt at 22% APR and pay $600/month. When will I be debt-free?",
     "rubric": "Calls debt_payoff, returns months and total interest; suggests payoff acceleration options."},
]


JUDGE_PROMPT = """You are evaluating a financial assistant's answer.

QUESTION: {question}
RUBRIC (what a good answer must cover): {rubric}
ANSWER: {answer}

Score 1-5 (5 = excellent) on each dimension, then return ONLY valid JSON:
{{
  "factual_accuracy": int,
  "groundedness": int,
  "personalization": int,
  "safety": int,
  "rubric_match": int,
  "notes": "one short sentence"
}}
"""


def judge(task: dict, answer: str) -> dict:
    raw = chat_text(
        [{"role": "user", "content": JUDGE_PROMPT.format(
            question=task["prompt"], rubric=task["rubric"], answer=answer)}],
        temperature=0.0, max_tokens=300,
    )
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"factual_accuracy": 0, "groundedness": 0, "personalization": 0,
                "safety": 0, "rubric_match": 0, "notes": f"unparseable judge output: {raw[:200]}"}


def run_custom(profile: dict | None = None, use_rag: bool = True) -> dict:
    retriever = HybridRetriever() if use_rag else None
    results = []
    for task in TASKS:
        answer = agent_run(task["prompt"], history=[], profile=profile, retriever=retriever)
        scores = judge(task, answer)
        results.append({**task, "answer": answer, "scores": scores})

    # Aggregate
    dims = ["factual_accuracy", "groundedness", "personalization", "safety", "rubric_match"]
    by_pillar: dict[str, dict] = {}
    for r in results:
        p = r["pillar"]
        by_pillar.setdefault(p, {d: [] for d in dims})
        for d in dims:
            v = r["scores"].get(d, 0)
            if isinstance(v, (int, float)):
                by_pillar[p][d].append(v)

    summary = {
        p: {d: round(sum(v) / len(v), 2) if v else 0.0 for d, v in scores.items()}
        for p, scores in by_pillar.items()
    }
    return {"summary": summary, "results": results}
