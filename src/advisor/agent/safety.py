"""Lightweight safety checks: refusal heuristics + disclaimer enforcement."""
from __future__ import annotations

import re

from advisor.llm.prompts import DISCLAIMER

DIRECTIVE_PATTERNS = [
    r"\bguaranteed (?:profit|return|gains?)\b",
    r"\brisk[- ]free\b",
    r"\bcan't lose\b",
    r"\bsure[- ]thing\b",
]

PROMPT_INJECTION_PATTERNS = [
    r"ignore (?:all |the )?(?:prior|previous|above) (?:instructions|prompt)",
    r"forget (?:everything|all instructions)",
    r"you are now",
    r"system prompt",
]


def check_user_input(text: str) -> dict:
    """Inspect a user message for risky patterns. Returns flags only — never blocks."""
    flags = []
    lower = text.lower()
    for p in PROMPT_INJECTION_PATTERNS:
        if re.search(p, lower):
            flags.append("possible_prompt_injection")
            break
    if re.search(r"bankruptcy|insolvenc", lower):
        flags.append("sensitive_financial_distress")
    return {"flags": flags}


def enforce_disclaimer(answer: str) -> str:
    """Append disclaimer if not already present."""
    if "educational information" in answer.lower() and "advice" in answer.lower():
        return answer
    return f"{answer.rstrip()}\n\n{DISCLAIMER}"


def scrub_directive_language(answer: str) -> str:
    """Soften/flag absolute claims. Best-effort regex pass."""
    out = answer
    for p in DIRECTIVE_PATTERNS:
        out = re.sub(p, "[unsupported claim removed]", out, flags=re.IGNORECASE)
    return out


def post_process(answer: str) -> str:
    return enforce_disclaimer(scrub_directive_language(answer))
