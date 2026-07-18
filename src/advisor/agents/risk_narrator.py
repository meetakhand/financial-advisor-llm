"""Risk Narrator — grounded LLM explanation of the deterministic risk band.

Sits between ``risk_agent`` and ``goal_agent`` in the pipeline. Takes the
``RiskResult`` produced by ``compute_risk`` plus the raw questionnaire
answers (and the customer's demographic capacity inputs) and asks the LLM
to explain *why* this customer landed in this band, in **exactly two
labelled lines**:

  **Why this band:** <one-sentence explanation of the tolerance/capacity
    signals that produced the band>
  **What the band means for the plan:** <one-sentence implication>

The LLM never re-computes the score or invents a different band — the
deterministic RiskResult is baked into the CONTEXT and the LLM is
instructed to reference those numbers rather than derive new ones.

Falls back to a deterministic template when ``LLM_PROVIDER=none``,
``HF_TOKEN`` is empty, or the LLM call errors — so the Risk Profile page
and the report always have an explanation block to render.

Output goes through ``screen_output`` for the disclaimer + directive scrub.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from advisor.config import settings
from advisor.domain.data import Customer
from advisor.domain.risk import QUESTIONNAIRE, RiskResult
from advisor.guardrails import screen_output


@dataclass
class RiskRationale:
    markdown: str
    source: str          # "llm" | "template" | "llm_error_fallback"
    provider: str = ""   # "groq" / "none" / etc.


_SYSTEM = (
    "You are FinAdvisor's risk-profile explainer. You produce EXACTLY two "
    "labelled lines (one sentence each, max ~25 words per line) explaining "
    "the customer's risk band. You NEVER re-derive the score or propose a "
    "different band — the RiskResult in CONTEXT is authoritative. Every "
    "quantitative claim must come from CONTEXT. Tone: factual and "
    "non-directive. Never tell the user to buy or sell."
)


def _points_word(p: int) -> str:
    """Human label for a 0-3 answer point."""
    return {0: "most-conservative", 1: "conservative-leaning",
            2: "growth-leaning", 3: "most-aggressive"}.get(p, "neutral")


def _context_block(customer: Customer, risk: RiskResult,
                    answer_points: list[int]) -> str:
    """Fact sheet the LLM must ground its explanation in."""
    lines: list[str] = []
    lines.append(f"Customer: {customer.name}, age {customer.age}, "
                    f"income ${customer.annual_income:,.0f}, "
                    f"dependents {customer.dependents}")
    lines.append(
        f"RiskResult: band={risk.risk_band}, score={risk.risk_score}, "
        f"tolerance={risk.tolerance}/100, capacity={risk.capacity}/100"
    )
    lines.append(f"Band description (from the domain rulebook): {risk.description}")
    lines.append("")
    lines.append("Questionnaire answers (0=most conservative, 3=most aggressive):")
    for i, q in enumerate(QUESTIONNAIRE):
        if i >= len(answer_points):
            break
        pts = answer_points[i]
        opts = q["options"]
        chosen_label = opts[pts][0] if 0 <= pts < len(opts) else "(unknown)"
        lines.append(
            f"  - {q['id']}: {pts}/3 ({_points_word(pts)}) — "
            f"\"{chosen_label}\""
        )
    lines.append("")
    lines.append(
        "Deterministic scoring rule (for context, do not re-compute): "
        "risk_score = round(0.6 * tolerance + 0.4 * capacity). "
        "Bands: <55 Moderate, 55-74 Growth, >=75 Aggressive."
    )
    return "\n".join(lines)


def _template_rationale(customer: Customer, risk: RiskResult,
                          answer_points: list[int]) -> str:
    """Deterministic 2-line explanation used when the LLM is off."""
    avg = sum(answer_points) / len(answer_points) if answer_points else 1.5
    if avg >= 2.0:
        tol_word = "growth-leaning"
    elif avg <= 1.0:
        tol_word = "conservative"
    else:
        tol_word = "middle-of-the-road"

    horizon_years = max(60 - customer.age, 0)

    why = (
        f"**Why this band:** {tol_word} answers (avg {avg:.1f}/3) gave "
        f"tolerance **{risk.tolerance:.0f}/100** and a ~{horizon_years}-yr "
        f"horizon with {customer.dependents} "
        f"dependent{'s' if customer.dependents != 1 else ''} gave capacity "
        f"**{risk.capacity:.0f}/100**, blending to "
        f"**{risk.risk_score}/100** in the **{risk.risk_band}** band."
    )
    means = (
        f"**What the band means for the plan:** it anchors the "
        f"{risk.risk_band}-model portfolio and sets the expected-return "
        f"and volatility assumptions the goal projection uses."
    )
    return "\n\n".join([why, means])


_WHY_LABEL = "**Why this band:**"
_MEANS_LABEL = "**What the band means for the plan:**"


def _first_sentence(text: str) -> str:
    """Return the first sentence of ``text`` (stop at first '.', '!', '?' or newline)."""
    text = text.strip()
    if not text:
        return ""
    match = re.search(r"[.!?](?:\s|$)|\n", text)
    if match:
        end = match.end()
        # Include the terminator if it was punctuation; strip a trailing newline.
        return text[:end].rstrip()
    return text


def _enforce_two_lines(raw: str) -> str:
    """Hard-cap the LLM output to exactly two labelled lines, one sentence each.

    The LLM often ignores the "one sentence" rule and emits multi-sentence
    paragraphs under each label. We split on the two known labels and keep
    only the first sentence of each section, so the rendered response can't
    balloon regardless of what the model produced.
    """
    text = raw.replace("\r\n", "\n").strip()
    if _WHY_LABEL not in text or _MEANS_LABEL not in text:
        return ""  # malformed / truncated — signal caller to fall back to template

    _, _, after_why = text.partition(_WHY_LABEL)
    why_body, _, after_means_marker = after_why.partition(_MEANS_LABEL)
    why_sentence = _first_sentence(why_body)
    means_sentence = _first_sentence(after_means_marker)
    if not why_sentence or not means_sentence:
        return ""
    return f"{_WHY_LABEL} {why_sentence}\n\n{_MEANS_LABEL} {means_sentence}"


def _llm_rationale(context: str) -> str:
    from advisor.llm.client import chat_text
    user = (
        "Using ONLY the facts in the CONTEXT below, write EXACTLY two "
        "labelled lines explaining this customer's risk band. Use these "
        "labels verbatim, each on its own line:\n"
        "  **Why this band:** <one sentence, ~25 words max, citing the "
        "tolerance and capacity numbers from CONTEXT and the drivers that "
        "produced them (questionnaire lean + horizon/income/dependents)>\n"
        "  **What the band means for the plan:** <one sentence, ~25 words "
        "max, on what this band anchors downstream (model portfolio, "
        "expected return, volatility)>\n\n"
        "Hard rules:\n"
        "- Exactly two lines. No paragraphs, no bullets, no extra headers, "
        "no preamble, no follow-up sentences.\n"
        "- Reference the numbers in CONTEXT verbatim — do NOT recompute.\n"
        "- Do NOT propose a different band; the RiskResult is authoritative.\n"
        "- Do NOT tell the user to buy or sell.\n\n"
        f"CONTEXT:\n{context}"
    )
    return chat_text(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        temperature=0.2, max_tokens=30,
    )


def narrate_risk(customer: Customer, risk: RiskResult,
                  answer_points: list[int]) -> RiskRationale:
    """Produce a 2-line explanation of the deterministic risk band.

    Deterministic template is the floor; the LLM is layered on top when
    available. Output goes through ``screen_output`` for the disclaimer
    + directive scrub.
    """
    template = _template_rationale(customer, risk, answer_points)

    if settings.llm_provider == "none" or not settings.hf_token:
        return RiskRationale(
            markdown=screen_output(template), source="template", provider="none",
        )

    try:
        context = _context_block(customer, risk, answer_points)
        raw = _llm_rationale(context)
        trimmed = _enforce_two_lines(raw) if raw else ""
        if not trimmed or len(trimmed.strip()) < 20:
            return RiskRationale(
                markdown=screen_output(template),
                source="llm_error_fallback",
                provider=settings.llm_provider,
            )
        return RiskRationale(
            markdown=screen_output(trimmed),
            source="llm",
            provider=settings.llm_provider,
        )
    except Exception:
        return RiskRationale(
            markdown=screen_output(template),
            source="llm_error_fallback",
            provider=settings.llm_provider,
        )


__all__ = ["RiskRationale", "narrate_risk"]
