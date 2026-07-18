"""Recommendation Narrator — grounded LLM rationale over the deterministic bundle.

Sits after ``recommend_agent`` in the pipeline. Takes the finished
``RecommendationBundle`` plus the numbers that produced it (risk, goal, portfolio,
benchmark) and asks the LLM for a 3-paragraph rationale:

  1. Why the AI-suggested model fits this customer.
  2. What concentration / drift / horizon risks are visible in the numbers.
  3. What to watch as the plan runs.

The LLM never invents allocations — the numbers are baked into the prompt and it
is instructed to reference them, not compute new ones. Output goes through
``screen_output`` for the disclaimer + directive scrub.

Falls back to a deterministic template when ``LLM_PROVIDER=none``, ``HF_TOKEN``
is empty, or the LLM call errors — so the Recommendations page always has a
rationale block to render.
"""
from __future__ import annotations

from dataclasses import dataclass

from advisor.agents.benchmark_agent import BenchmarkResult
from advisor.agents.goal_agent import GoalPlan
from advisor.agents.portfolio_agent import PortfolioAnalysis
from advisor.agents.recommend_agent import RecommendationBundle
from advisor.config import settings
from advisor.domain.data import Customer
from advisor.domain.risk import RiskResult
from advisor.guardrails import screen_output
from advisor.llm.prompts import DISCLAIMER


@dataclass
class RecommendationRationale:
    markdown: str
    source: str          # "llm" | "template" | "llm_error_fallback"
    provider: str = ""   # e.g. "groq" or "none"


_SYSTEM = (
    "You are FinAdvisor's rationale writer. You explain WHY a deterministic "
    "recommendation fits a specific customer. You NEVER invent numbers, "
    "allocations, or model portfolios — every quantitative claim must come "
    "from the CONTEXT block below. If a fact isn't in the context, don't "
    "state it. Keep the tone factual and non-directive. Do not tell the user "
    "to buy or sell anything; frame everything as 'considerations' or 'things "
    "to monitor'."
)


def _context_block(customer: Customer, risk: RiskResult, goal: GoalPlan,
                     portfolio: PortfolioAnalysis, benchmark: BenchmarkResult,
                     rec: RecommendationBundle, journey: str) -> str:
    """Compact fact sheet the LLM must ground its rationale in."""
    ai_opt = next((o for o in rec.options if o.is_ai_suggested), None)
    lines: list[str] = []
    lines.append(f"Customer: {customer.name}, age {customer.age}, "
                    f"income ${customer.annual_income:,.0f}, "
                    f"dependents {customer.dependents}")
    lines.append(f"Journey: {journey}")
    lines.append(f"Risk band: {risk.risk_band} (score {risk.risk_score} — "
                    f"tolerance {risk.tolerance}, capacity {risk.capacity})")
    lines.append(
        f"Goal: target ${goal.target_amount_today:,.0f} in today's dollars "
        f"(${goal.target_amount_future:,.0f} inflated to year {goal.years:.0f}); "
        f"projected corpus ${goal.projected_amount:,.0f}; "
        f"funding gap ${goal.funding_gap:,.0f}; "
        f"required SIP ${goal.required_monthly_sip:,.0f}/mo; "
        f"success probability {goal.success_prob * 100:.0f}%"
    )
    if portfolio.has_holdings:
        lines.append(
            f"Portfolio: market value ${portfolio.total_market_value:,.0f}, "
            f"P/L ${portfolio.total_gain_loss:,.0f} "
            f"({portfolio.total_gain_loss_pct:.1f}%)"
        )
        alloc_str = ", ".join(f"{k} {v:.1f}%" for k, v in portfolio.allocation_pct.items())
        lines.append(f"Current allocation: {alloc_str}")
        # Concentration: any single asset class ≥ 60% is worth flagging.
        concentrated = [k for k, v in portfolio.allocation_pct.items() if v >= 60]
        if concentrated:
            lines.append(f"Concentration flag: >=60% in {', '.join(concentrated)}")
    else:
        lines.append("Portfolio: no holdings on file yet")
    lines.append(
        f"Benchmark: proxy {benchmark.proxy_ticker}, "
        f"portfolio expected {benchmark.portfolio_expected_return * 100:.1f}%, "
        f"benchmark {benchmark.benchmark_expected_return * 100:.1f}%, "
        f"excess {benchmark.excess_return * 100:+.1f}%"
    )
    lines.append(f"AI-suggested model: {rec.ai_suggested}")
    if ai_opt is not None:
        target_str = ", ".join(
            f"{k} {v:.0f}%" for k, v in ai_opt.target_allocation_pct.items()
        )
        lines.append(
            f"AI-suggested target allocation: {target_str}; "
            f"expected return {ai_opt.expected_return * 100:.1f}%, "
            f"volatility {ai_opt.volatility * 100:.1f}%, "
            f"fit score {ai_opt.fit_score:.0f}/100"
        )
        if ai_opt.rebalancing_actions:
            actions = "; ".join(
                f"{a['action']} {a['asset_class']} by {a['delta_pct']:.0f}pp"
                for a in ai_opt.rebalancing_actions
            )
            lines.append(f"Rebalancing actions to reach target: {actions}")
    other_models = [o.model for o in rec.options if not o.is_ai_suggested]
    if other_models:
        lines.append(f"Alternative models offered: {', '.join(other_models)}")
    return "\n".join(lines)


def _template_rationale(customer: Customer, risk: RiskResult, goal: GoalPlan,
                          portfolio: PortfolioAnalysis, benchmark: BenchmarkResult,
                          rec: RecommendationBundle, journey: str) -> str:
    """Deterministic 3-paragraph rationale used when the LLM is off."""
    ai_opt = next((o for o in rec.options if o.is_ai_suggested), None)

    # ---- Paragraph 1: why this model fits ----
    p1 = (
        f"**Why {rec.ai_suggested} fits {customer.name}.** "
        f"The risk questionnaire places {customer.name} in the **{risk.risk_band}** "
        f"band (score {risk.risk_score}, tolerance {risk.tolerance}, capacity "
        f"{risk.capacity}). For a **{journey}** journey over "
        f"{goal.years:.0f} years, the {rec.ai_suggested} model targets "
    )
    if ai_opt is not None:
        p1 += (f"an expected return of {ai_opt.expected_return * 100:.1f}% with "
                f"{ai_opt.volatility * 100:.1f}% volatility, and matches the "
                f"customer's current holdings with a fit score of "
                f"{ai_opt.fit_score:.0f}/100.")
    else:
        p1 += "the risk-appropriate blend of asset classes for this band."

    # ---- Paragraph 2: risks visible in the numbers ----
    risk_bits: list[str] = []
    if goal.funding_gap > 0:
        risk_bits.append(
            f"a funding gap of ${goal.funding_gap:,.0f} — closing it requires "
            f"about ${goal.required_monthly_sip:,.0f}/mo in contributions"
        )
    if portfolio.has_holdings:
        concentrated = [(k, v) for k, v in portfolio.allocation_pct.items() if v >= 60]
        if concentrated:
            k, v = concentrated[0]
            risk_bits.append(
                f"a concentrated position — {v:.0f}% of the portfolio sits in "
                f"{k}, which raises single-factor risk"
            )
        if ai_opt and ai_opt.rebalancing_actions:
            n = len(ai_opt.rebalancing_actions)
            risk_bits.append(
                f"{n} rebalancing action{'s' if n != 1 else ''} needed to reach "
                f"the {rec.ai_suggested} target — worth staging over multiple "
                "tax years if positions have embedded gains"
            )
    if journey == "Buy Home" and goal.years <= 5:
        risk_bits.append(
            f"a short horizon ({goal.years:.0f} years) — sequence-of-returns risk "
            "dominates, so the plan caps expected return at 4.5% to prioritize "
            "capital preservation"
        )
    if not risk_bits:
        risk_bits.append(
            "no immediate red flags in the numbers — the plan and portfolio "
            "are internally consistent for this risk band"
        )

    def _sentence(s: str) -> str:
        s = s.strip()
        if not s:
            return ""
        s = s[0].upper() + s[1:]
        return s if s.endswith(".") else s + "."

    p2 = "**What to watch.** " + _sentence(risk_bits[0])
    if len(risk_bits) > 1:
        p2 += " " + " ".join("Also: " + _sentence(s) for s in risk_bits[1:])

    # ---- Paragraph 3: as the plan runs ----
    p3_bits = [
        f"Re-run the projection every 12 months or on any material change to "
        f"income, contribution capacity, or dependents.",
    ]
    if benchmark.excess_return < 0:
        p3_bits.append(
            f"The current blend is projected to trail the {benchmark.proxy_ticker} "
            f"benchmark by {abs(benchmark.excess_return) * 100:.1f}pp — that's a "
            "signal to revisit either the model choice or the underlying holdings."
        )
    else:
        p3_bits.append(
            f"The current blend is projected to exceed the {benchmark.proxy_ticker} "
            f"benchmark by {benchmark.excess_return * 100:.1f}pp given the risk taken."
        )
    p3_bits.append(
        f"If the funding gap widens, consider raising the SIP toward "
        f"${goal.required_monthly_sip:,.0f}/mo before moving up a risk band."
    )
    p3 = "**How to run the plan.** " + " ".join(p3_bits)

    return "\n\n".join([p1, p2, p3])


def _llm_rationale(context: str) -> str:
    from advisor.llm.client import chat_text
    user = (
        "Using ONLY the facts in the CONTEXT below, write a 3-paragraph "
        "rationale for this customer's recommendation. Use these three "
        "paragraph headers verbatim (bold-formatted):\n"
        "  **Why this model fits.**\n"
        "  **What to watch.**\n"
        "  **How to run the plan.**\n\n"
        "Rules:\n"
        "- Every number you cite must appear in the CONTEXT.\n"
        "- Do NOT invent new allocations or model portfolios.\n"
        "- Do NOT tell the user to buy or sell — frame as 'considerations' "
        "or 'things to monitor'.\n"
        "- 2-4 sentences per paragraph.\n\n"
        f"CONTEXT:\n{context}"
    )
    return chat_text(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        temperature=0.2, max_tokens=650,
    )


def narrate_recommendation(customer: Customer, journey: str, risk: RiskResult,
                             goal: GoalPlan, portfolio: PortfolioAnalysis,
                             benchmark: BenchmarkResult,
                             rec: RecommendationBundle) -> RecommendationRationale:
    """Produce a 3-paragraph rationale grounded in the deterministic bundle.

    Deterministic template is the floor; the LLM is layered on top when
    available. All output is passed through ``screen_output`` for the
    disclaimer + directive scrub.
    """
    template = _template_rationale(customer, risk, goal, portfolio,
                                       benchmark, rec, journey)

    if settings.llm_provider == "none" or not settings.hf_token:
        return RecommendationRationale(
            markdown=screen_output(template), source="template", provider="none",
        )

    try:
        context = _context_block(customer, risk, goal, portfolio, benchmark, rec, journey)
        raw = _llm_rationale(context)
        # If the LLM returned something empty or too short to be a rationale,
        # keep the template — never render a stub.
        if not raw or len(raw.strip()) < 80:
            return RecommendationRationale(
                markdown=screen_output(template),
                source="llm_error_fallback",
                provider=settings.llm_provider,
            )
        return RecommendationRationale(
            markdown=screen_output(raw),
            source="llm",
            provider=settings.llm_provider,
        )
    except Exception:
        return RecommendationRationale(
            markdown=screen_output(template),
            source="llm_error_fallback",
            provider=settings.llm_provider,
        )


__all__ = ["RecommendationRationale", "narrate_recommendation"]
