"""Guardrails — input screening + output post-processing.

Wraps every advisor turn and the final Report emission. Input screening
detects prompt-injection / out-of-scope / distress; output screening scrubs
directive language and enforces the US disclaimer.

Deterministic — no LLM calls in this layer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from advisor.llm.prompts import DISCLAIMER

DISCLAIMER_US = DISCLAIMER

BLOCKED_PATTERNS = [
    r"ignore (?:all |the )?(?:prior|previous|above) (?:instructions|prompt)",
    r"forget (?:everything|all instructions)",
    r"you are now",
    r"reveal (?:your )?system prompt",
    r"disregard (?:the )?rules",
]

OUT_OF_SCOPE_PATTERNS = [
    r"\bcrypto (?:trading|pump)\b",
    r"\binsider (?:tip|info)\b",
    r"\bday[- ]trad(?:e|ing) (?:advice|tips?)\b",
    r"\bpenny stocks?\b",
]

DIRECTIVE_PATTERNS = [
    r"\byou (?:must|should) (?:buy|sell) (?:now|immediately|today)\b",
    r"\bguaranteed (?:profit|return|gains?)\b",
    r"\brisk[- ]free\b",
    r"\bcan't lose\b",
    r"\bsure[- ]thing\b",
]

DISTRESS_PATTERNS = [r"\bbankruptc(?:y|ies)\b", r"\binsolven(?:cy|t)\b"]


BLOCKED_REPLY = (
    "I can't help with that request. If you're looking for educational "
    "information on investing, retirement, or financial planning, I can "
    "walk through concepts and grounded analysis instead."
)


@dataclass(frozen=True)
class ScreenResult:
    blocked: bool
    flags: list[str]
    reason: str


def screen_input(text: str) -> ScreenResult:
    lower = text.lower()
    flags = []
    for p in BLOCKED_PATTERNS:
        if re.search(p, lower):
            return ScreenResult(blocked=True, flags=["prompt_injection"],
                                reason="prompt-injection pattern")
    for p in OUT_OF_SCOPE_PATTERNS:
        if re.search(p, lower):
            return ScreenResult(blocked=True, flags=["out_of_scope"],
                                reason="out-of-scope request")
    for p in DISTRESS_PATTERNS:
        if re.search(p, lower):
            flags.append("financial_distress")
            break
    return ScreenResult(blocked=False, flags=flags, reason="")


def scrub_directives(text: str) -> str:
    out = text
    for p in DIRECTIVE_PATTERNS:
        out = re.sub(p, "[unsupported claim removed]", out, flags=re.IGNORECASE)
    return out


def enforce_disclaimer(text: str) -> str:
    if DISCLAIMER_US.strip()[:40].lower() in text.lower():
        return text
    if "educational" in text.lower() and "not" in text.lower() and "advice" in text.lower():
        return text
    return f"{text.rstrip()}\n\n{DISCLAIMER_US}"


def screen_output(text: str) -> str:
    """Post-process an assistant response: scrub directives + append disclaimer."""
    return enforce_disclaimer(scrub_directives(text))


def apply_guardrails(user_text: str, generate_fn: Callable[[str], str]) -> tuple[str, bool]:
    """Screen input, run ``generate_fn`` if safe, screen output.

    Returns (response, was_blocked). was_blocked=True means the user's
    message was refused before reaching the LLM; the caller should surface
    the reply as-is and skip logging it as a real turn.
    """
    result = screen_input(user_text)
    if result.blocked:
        return screen_output(BLOCKED_REPLY), True
    raw = generate_fn(user_text)
    return screen_output(raw), False
