"""Parse free-text asks into structured profile changes.

A tiny, deterministic recognizer for the demo. It recognizes a fixed
vocabulary of edits — monthly contribution, retirement age, home price,
target college cost, journey switch, model portfolio — and returns a
``ProposedChange`` the UI can present as a confirmation card. Anything
outside the vocabulary returns ``None`` so the caller falls through to
normal RAG Q&A.

The parser is intentionally regex-based (not LLM) so it works when
``LLM_PROVIDER=none``. An LLM upgrade would swap ``propose_change`` for
a structured-output prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Supported change types the pipeline knows how to react to.
JOURNEY_ALIASES = {
    "retirement": "Retirement Planning",
    "retirement planning": "Retirement Planning",
    "retire": "Retirement Planning",
    "child education": "Child Education",
    "college": "Child Education",
    "education": "Child Education",
    "buy home": "Buy Home",
    "buy a home": "Buy Home",
    "home": "Buy Home",
    "house": "Buy Home",
    "financial q&a": "Financial Q&A",
    "financial qa": "Financial Q&A",
    "q&a": "Financial Q&A",
}

MODEL_ALIASES = {
    "moderate": "Moderate", "growth": "Growth", "aggressive": "Aggressive",
}


@dataclass
class ProposedChange:
    kind: str           # goal_input | journey | model
    field: str          # target_retirement_age | monthly_contribution | ...
    new_value: Any
    old_value: Any
    label: str          # user-facing "Increase monthly contribution → $1,500"
    reason: str = ""    # optional explanation for the confirmation card


# ---- helpers --------------------------------------------------------------

_MONEY_RE = re.compile(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(k|K|m|M)?")


def _parse_money(text: str) -> float | None:
    m = _MONEY_RE.search(text)
    if not m:
        return None
    raw, mult = m.group(1).replace(",", ""), (m.group(2) or "").lower()
    try:
        value = float(raw)
    except ValueError:
        return None
    if mult == "k":
        value *= 1_000
    elif mult == "m":
        value *= 1_000_000
    return value


def _current(goal_inputs: dict, key: str, default=None):
    return (goal_inputs or {}).get(key, default)


def _match_any(text: str, aliases: dict[str, str]) -> str | None:
    lower = text.lower()
    for alias, canonical in sorted(aliases.items(), key=lambda kv: -len(kv[0])):
        if alias in lower:
            return canonical
    return None


# ---- rules ---------------------------------------------------------------

def _rule_monthly_contribution(text: str, goal_inputs: dict) -> ProposedChange | None:
    if not re.search(r"(monthly\s+contribution|save|contribute|sip|per month|/month)",
                        text, re.I):
        return None
    amount = _parse_money(text)
    if amount is None:
        return None
    old = float(_current(goal_inputs, "monthly_contribution", 0.0) or 0.0)
    if abs(amount - old) < 1:
        return None
    return ProposedChange(
        kind="goal_input", field="monthly_contribution",
        new_value=amount, old_value=old,
        label=f"Monthly contribution: ${old:,.0f} → ${amount:,.0f}",
        reason="Updates the recurring savings assumption in the projection.",
    )


def _rule_retirement_age(text: str, goal_inputs: dict) -> ProposedChange | None:
    m = re.search(r"retire\s+(?:at|by)?\s*(?:age\s+)?(\d{2})", text, re.I)
    if not m:
        m = re.search(r"retirement\s+age\s+(?:to\s+)?(\d{2})", text, re.I)
    if not m:
        return None
    age = int(m.group(1))
    if not (40 <= age <= 90):
        return None
    old = int(_current(goal_inputs, "target_retirement_age", 65) or 65)
    if age == old:
        return None
    return ProposedChange(
        kind="goal_input", field="target_retirement_age",
        new_value=age, old_value=old,
        label=f"Retirement age: {old} → {age}",
        reason="Shortens/extends the compounding horizon and inflation window.",
    )


def _rule_desired_monthly_income(text: str, goal_inputs: dict) -> ProposedChange | None:
    if not re.search(r"(desired|target|need|want)\s+(?:monthly\s+)?income", text, re.I):
        return None
    amount = _parse_money(text)
    if amount is None:
        return None
    old = float(_current(goal_inputs, "desired_monthly_income", 0.0) or 0.0)
    if abs(amount - old) < 1:
        return None
    return ProposedChange(
        kind="goal_input", field="desired_monthly_income",
        new_value=amount, old_value=old,
        label=f"Desired monthly retirement income: ${old:,.0f} → ${amount:,.0f}",
        reason="Recomputes the 25× annual-income retirement target.",
    )


def _rule_home_price(text: str, goal_inputs: dict) -> ProposedChange | None:
    if not re.search(r"(home\s+price|house\s+price|buy\s+a?\s*(?:home|house))",
                        text, re.I):
        return None
    amount = _parse_money(text)
    if amount is None:
        return None
    old = float(_current(goal_inputs, "home_price", 0.0) or 0.0)
    if abs(amount - old) < 1:
        return None
    return ProposedChange(
        kind="goal_input", field="home_price",
        new_value=amount, old_value=old,
        label=f"Home price: ${old:,.0f} → ${amount:,.0f}",
        reason="Recomputes the down-payment target.",
    )


def _rule_college_cost(text: str, goal_inputs: dict) -> ProposedChange | None:
    if not re.search(r"(college|tuition|education)", text, re.I):
        return None
    amount = _parse_money(text)
    if amount is None:
        return None
    old = float(_current(goal_inputs, "target_cost_today", 0.0) or 0.0)
    if abs(amount - old) < 1:
        return None
    return ProposedChange(
        kind="goal_input", field="target_cost_today",
        new_value=amount, old_value=old,
        label=f"College target: ${old:,.0f} → ${amount:,.0f}",
        reason="Recomputes the tuition target with education-premium inflation.",
    )


def _rule_journey(text: str, current_journey: str) -> ProposedChange | None:
    if not re.search(r"(switch|change|set)\s+(?:to|the)?\s*(?:journey|plan|goal)?",
                        text, re.I):
        # Also allow "let's plan for retirement" style
        if not re.search(r"(plan\s+for|focus\s+on|help\s+with)", text, re.I):
            return None
    target = _match_any(text, JOURNEY_ALIASES)
    if not target or target == current_journey:
        return None
    return ProposedChange(
        kind="journey", field="primary_goal",
        new_value=target, old_value=current_journey,
        label=f"Journey: {current_journey or 'unset'} → {target}",
        reason="Switches the active planning journey and regenerates the pipeline.",
    )


def _rule_model(text: str, current_model: str) -> ProposedChange | None:
    if not re.search(r"(use|switch|change|move|set|pick)\s+(?:to\s+)?"
                        r"(?:the\s+)?(moderate|growth|aggressive)",
                        text, re.I):
        return None
    target = _match_any(text, MODEL_ALIASES)
    if not target or target == current_model:
        return None
    return ProposedChange(
        kind="model", field="active_model",
        new_value=target, old_value=current_model,
        label=f"Model portfolio: {current_model} → {target}",
        reason="Applies an override; recommendations recompute for the new band.",
    )


# ---- public entrypoint ---------------------------------------------------

def propose_change(text: str, *, goal_inputs: dict | None,
                     current_journey: str | None,
                     current_model: str | None) -> ProposedChange | None:
    """Try each rule in turn. First match wins. None => no change intent."""
    gi = goal_inputs or {}
    for rule, args in (
        (_rule_monthly_contribution, (text, gi)),
        (_rule_retirement_age,       (text, gi)),
        (_rule_desired_monthly_income, (text, gi)),
        (_rule_home_price,           (text, gi)),
        (_rule_college_cost,         (text, gi)),
        (_rule_journey,              (text, current_journey or "")),
        (_rule_model,                (text, current_model or "")),
    ):
        change = rule(*args)
        if change is not None:
            return change
    return None


__all__ = ["ProposedChange", "propose_change"]
