"""NexWealth MCP server — every tool is a thin wrapper around the
existing advisor package. The Streamlit app is untouched; this file
only *reads* from src/advisor/*.

Run: python -m nexwealth_mcp
"""
from __future__ import annotations

import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

# Make src/ importable — same trick the Streamlit pages use.
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from advisor.agents.benchmark_agent import run_benchmarking as _run_benchmarking  # noqa: E402
from advisor.agents.goal_agent import (  # noqa: E402
    plan_buy_home as _plan_buy_home,
    plan_child_education as _plan_child_education,
    plan_retirement as _plan_retirement,
)
from advisor.agents.orchestrator import run_pipeline as _run_pipeline  # noqa: E402
from advisor.agents.portfolio_agent import analyze_portfolio as _analyze_portfolio  # noqa: E402
from advisor.agents.recommend_agent import run_recommendation as _run_recommendation  # noqa: E402
from advisor.agents.recommendation_narrator import narrate_recommendation as _narrate_rec  # noqa: E402
from advisor.agents.report_agent import build_markdown_report as _build_report  # noqa: E402
from advisor.agents.risk_agent import run_risk_profiling as _score_risk  # noqa: E402
from advisor.agents.risk_narrator import narrate_risk as _narrate_risk  # noqa: E402
from advisor.domain.data import (  # noqa: E402
    commit_hitl_decision as _commit_hitl,
    get_customer as _get_customer,
    get_hitl_log as _get_hitl_log,
    latest_committed_for_journey as _latest_committed,
    list_customers as _list_customers,
)
from advisor.rag.retrieve import HybridRetriever  # noqa: E402


mcp = FastMCP("nexwealth")


# ---------- helpers ----------

def _to_dict(obj):
    """Coerce dataclass/pydantic/etc. into plain JSON-safe dicts."""
    if obj is None:
        return None
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, list):
        return [_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


def _customer_or_err(customer_id: int):
    c = _get_customer(customer_id)
    if not c:
        raise ValueError(f"No customer with id={customer_id}")
    return c


# ---------- customer lookup ----------

@mcp.tool()
def list_customers() -> list[dict]:
    """List all customers on file. Returns id, name, age, income,
    dependents, primary_goal for each — the RM uses this to pick a
    customer to load."""
    return [
        {"id": c.id, "external_id": c.external_id, "name": c.name,
         "age": c.age, "annual_income": c.annual_income,
         "dependents": c.dependents, "primary_goal": c.primary_goal}
        for c in _list_customers()
    ]


@mcp.tool()
def get_customer(customer_id: int) -> dict:
    """Fetch the full customer record: profile, saved risk answers,
    goal_inputs, and holdings. This is the ground truth for every
    downstream pipeline step."""
    c = _customer_or_err(customer_id)
    return {
        "id": c.id, "external_id": c.external_id, "name": c.name,
        "age": c.age, "annual_income": c.annual_income,
        "dependents": c.dependents, "primary_goal": c.primary_goal,
        "risk_answers": c.risk_answers,
        "goal_inputs": c.goal_inputs,
        "holdings": [_to_dict(h) for h in (c.holdings or [])],
    }


# ---------- risk ----------

@mcp.tool()
def score_risk(customer_id: int, answers: list[int] | None = None) -> dict:
    """Score the customer's risk using the 5-question tolerance
    questionnaire + capacity (age, income, dependents). If `answers`
    is omitted, uses the answers saved on the customer record. Returns
    band (Moderate / Growth / Aggressive), score (0-100), tolerance,
    capacity, and a plain-English description."""
    c = _customer_or_err(customer_id)
    ans = answers if answers is not None else c.risk_answers
    if not ans:
        raise ValueError("No risk answers provided and none saved on customer.")
    return _to_dict(_score_risk(ans, c.age, c.annual_income, c.dependents))


@mcp.tool()
def narrate_risk(customer_id: int, answers: list[int] | None = None) -> dict:
    """Produce a grounded LLM rationale for the risk band. Never sees
    customer PII — only the numeric result of `score_risk`. Falls back
    to a deterministic template on LLM failure; the return payload
    always includes a `source` field ('llm' or 'template' or
    'llm_error_fallback')."""
    c = _customer_or_err(customer_id)
    ans = answers if answers is not None else c.risk_answers
    risk = _score_risk(ans, c.age, c.annual_income, c.dependents)
    return _to_dict(_narrate_risk(c, risk, ans))


# ---------- goal ----------

@mcp.tool()
def plan_retirement(customer_id: int, target_retirement_age: int,
                    desired_monthly_income: float,
                    current_savings: float | None = None,
                    monthly_contribution: float | None = None,
                    risk_band: str | None = None) -> dict:
    """Retirement plan: target amount (today $ and inflated), projected
    corpus, funding ratio, MC p10/p50/p90, outlook, required SIP.
    Missing inputs are taken from the customer's saved goal_inputs.
    Missing risk_band is computed on the fly from saved answers."""
    c = _customer_or_err(customer_id)
    gi = c.goal_inputs or {}
    if current_savings is None:
        current_savings = float(gi.get("current_savings", 0))
    if monthly_contribution is None:
        monthly_contribution = float(gi.get("monthly_contribution", 0))
    if not risk_band:
        risk_band = _score_risk(c.risk_answers, c.age,
                                 c.annual_income, c.dependents).risk_band
    plan = _plan_retirement(c.age, target_retirement_age, desired_monthly_income,
                             current_savings, monthly_contribution, risk_band)
    return _to_dict(plan)


@mcp.tool()
def plan_education(customer_id: int, child_current_age: int,
                    target_cost_today: float,
                    current_savings: float | None = None,
                    monthly_contribution: float | None = None,
                    risk_band: str | None = None,
                    child_start_age: int = 18) -> dict:
    """Child education plan. CPI premium is baked in (CPI+2%)."""
    c = _customer_or_err(customer_id)
    gi = c.goal_inputs or {}
    if current_savings is None:
        current_savings = float(gi.get("current_savings", 0))
    if monthly_contribution is None:
        monthly_contribution = float(gi.get("monthly_contribution", 0))
    if not risk_band:
        risk_band = _score_risk(c.risk_answers, c.age,
                                 c.annual_income, c.dependents).risk_band
    plan = _plan_child_education(child_current_age, target_cost_today,
                                   current_savings, monthly_contribution,
                                   risk_band, child_start_age=child_start_age)
    return _to_dict(plan)


@mcp.tool()
def plan_home(customer_id: int, home_price: float, down_payment_pct: float,
               years_to_buy: int,
               current_savings: float | None = None,
               monthly_contribution: float | None = None,
               risk_band: str | None = None) -> dict:
    """Home-purchase plan targeting the down payment corpus."""
    c = _customer_or_err(customer_id)
    gi = c.goal_inputs or {}
    if current_savings is None:
        current_savings = float(gi.get("current_savings", 0))
    if monthly_contribution is None:
        monthly_contribution = float(gi.get("monthly_contribution", 0))
    if not risk_band:
        risk_band = _score_risk(c.risk_answers, c.age,
                                 c.annual_income, c.dependents).risk_band
    plan = _plan_buy_home(home_price, down_payment_pct, years_to_buy,
                            current_savings, monthly_contribution, risk_band)
    return _to_dict(plan)


# ---------- portfolio / benchmark / recommend ----------

@mcp.tool()
def analyze_portfolio(customer_id: int, allow_live: bool = True) -> dict:
    """Analyze the customer's holdings: market value, cost basis, P/L,
    per-holding freshness (live / cached / seed), and current
    allocation %. `allow_live=True` hits Alpha Vantage; the three-tier
    price fallback (live → CSV → seed) is inside the agent."""
    c = _customer_or_err(customer_id)
    return _to_dict(_analyze_portfolio(c.holdings or [], allow_live=allow_live))


@mcp.tool()
def run_benchmark(model_name: str, allow_live: bool = True) -> dict:
    """Live 5Y CAGR + realized vol for the risk-band-matched iShares
    peer ETF (Moderate→AOM / Growth→AOR / Aggressive→AOA). Falls back
    to illustrative long-run constants when the AV series is
    unavailable. Response includes `benchmark_source` ('live_5y' or
    'illustrative') and the weekly-obs count."""
    return _to_dict(_run_benchmarking(model_name, allow_live=allow_live))


@mcp.tool()
def generate_recommendations(customer_id: int,
                               model_name: str | None = None) -> dict:
    """Produce 3 model options (one below, AI-suggested, one above)
    with fit scores and rebalancing actions. Uses the customer's
    current allocation as the anchor."""
    c = _customer_or_err(customer_id)
    if not model_name:
        model_name = _score_risk(c.risk_answers, c.age,
                                  c.annual_income, c.dependents).risk_band
    analysis = _analyze_portfolio(c.holdings or [], allow_live=False)
    return _to_dict(_run_recommendation(model_name, analysis.allocation_pct))


@mcp.tool()
def narrate_recommendation(customer_id: int, journey: str | None = None) -> dict:
    """Grounded LLM rationale for the recommendation. Receives
    deterministic pipeline outputs only — never PII. Falls back to
    template on LLM failure with a visible source badge in `source`.

    For deep integration, prefer `run_pipeline` which chains all steps
    server-side and returns a fully-narrated result in one round-trip.
    """
    c = _customer_or_err(customer_id)
    journey = journey or c.primary_goal or "Retirement Planning"
    result = _run_pipeline(c, journey, c.goal_inputs or {}, allow_live_prices=False)
    return _to_dict(result.rationale)


# ---------- composite pipeline ----------

@mcp.tool()
def run_pipeline(customer_id: int, journey: str | None = None,
                  goal_inputs: dict | None = None,
                  allow_live_prices: bool = True) -> dict:
    """Composite: runs the full 8-step planning pipeline server-side
    (risk → risk narrate → goal → portfolio → benchmark → recommend →
    recommend narrate → report). Opens a HITL review row and returns
    the `hitl_id` — commit an Approve/Reject/Override via
    `commit_hitl_decision(hitl_id, ...)`.

    Preferred entry point for the annual-review sub-skill.
    """
    c = _customer_or_err(customer_id)
    journey = journey or c.primary_goal or "Retirement Planning"
    inputs = goal_inputs if goal_inputs is not None else (c.goal_inputs or {})
    result = _run_pipeline(c, journey, inputs, allow_live_prices=allow_live_prices)

    return {
        "customer_id": result.customer_id,
        "journey": result.journey,
        "hitl_id": result.hitl_id,
        "agent_run_id": result.agent_run_id,
        "risk": _to_dict(result.risk),
        "risk_rationale": _to_dict(result.risk_rationale),
        "goal": _to_dict(result.goal),
        "portfolio": _to_dict(result.portfolio),
        "benchmark": _to_dict(result.benchmark),
        "recommendation": _to_dict(result.recommendation),
        "rationale": _to_dict(result.rationale),
        "warnings": result.warnings,
        "prior_hitl": result.prior_hitl,
        "report_markdown": result.report_markdown,
    }


# ---------- HITL ----------

@mcp.tool()
def get_last_committed_decision(customer_id: int, journey: str) -> dict | None:
    """Return the customer's most recent committed HITL decision for
    this journey, or null if none exists. The RM uses this as the
    baseline for annual-review delta reporting."""
    return _latest_committed(customer_id, journey)


@mcp.tool()
def get_hitl_log(customer_id: int, only_committed: bool = True) -> list[dict]:
    """Full HITL history for a customer — every AI suggestion + human
    override with rationale, in reverse chronological order."""
    return _get_hitl_log(customer_id, only_committed=only_committed)


@mcp.tool()
def commit_hitl_decision(hitl_id: int, final_action: str,
                           final_choice: str,
                           rationale: str | None = None,
                           override_allocation: dict | None = None) -> dict:
    """Commit the RM's Approve / Reject / Override decision to the
    HITL log. `final_action` must be one of: 'approve', 'reject',
    'override'. On 'override', supply `override_allocation` as a
    {asset_class: pct} dict summing to 100.

    Do not call without explicit RM confirmation."""
    if final_action not in {"approve", "reject", "override"}:
        raise ValueError(f"final_action must be approve|reject|override, got {final_action!r}")
    _commit_hitl(hitl_id, final_choice=final_choice, final_action=final_action,
                  rationale=rationale, override_allocation=override_allocation)
    return {"hitl_id": hitl_id, "final_action": final_action,
             "final_choice": final_choice, "committed": True}


# ---------- report ----------

@mcp.tool()
def build_report(customer_id: int, journey: str | None = None,
                  save_to: str | None = None) -> dict:
    """Rebuild the full markdown report using the latest committed
    HITL decision. If `save_to` is given, writes the markdown to disk
    at that absolute path and returns the path. Otherwise returns the
    markdown string only."""
    c = _customer_or_err(customer_id)
    journey = journey or c.primary_goal or "Retirement Planning"
    result = _run_pipeline(c, journey, c.goal_inputs or {}, allow_live_prices=False)
    latest = _latest_committed(c.id, journey)
    markdown = _build_report(
        c, journey, result.goal, result.risk,
        result.recommendation.active_model,
        result.portfolio, result.benchmark, result.recommendation,
        hitl_decision=latest,
        rationale_markdown=(result.rationale.markdown if result.rationale else None),
        risk_rationale_markdown=(result.risk_rationale.markdown if result.risk_rationale else None),
    )
    out = {"markdown": markdown, "customer_external_id": c.external_id,
            "journey": journey}
    if save_to:
        Path(save_to).write_text(markdown, encoding="utf-8")
        out["saved_to"] = save_to
    return out


# ---------- RAG ----------

_retriever: HybridRetriever | None = None


def _get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


@mcp.tool()
def search_finance_kb(query: str, k: int = 5) -> list[dict]:
    """Hybrid RAG search (BM25 + dense, RRF-fused) over the finance
    corpus (SEC / IRS / FINRA / glossary). Returns snippets with
    `source` citations. Use for regulatory figures, definitions, and
    general Q&A the RM would otherwise look up manually."""
    return _get_retriever().search(query, k=k)
