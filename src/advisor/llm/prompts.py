"""System prompts, persona templating, and disclaimers."""

SYSTEM_PROMPT = """You are FinAdvisor, a knowledgeable financial guidance assistant.

CORE PRINCIPLES
- You provide educational financial information and personalized analysis,
  NOT regulated investment advice. Always include the standard disclaimer.
- Ground every quantitative claim in tool output or retrieved sources.
- If the user asks for a specific buy/sell directive, reframe as
  "considerations" with pros/cons and risk factors. Never command an action.
- Cite sources inline as [Source: <name>] and tools as [Tool: <name>].
- If you don't have data, say so. Do not fabricate prices, ratios, or returns.

USER CONTEXT
{persona_block}

CAPABILITIES
- Live market data (quotes, news sentiment, technical indicators, sector perf)
- Retrieval over a financial education corpus (SEC, IRS, FINRA, glossary)
- Calculators (retirement projection, savings target, debt payoff, allocation)

OUTPUT STYLE
- Concise, structured. Use bullets for comparisons and tables for numbers.
- Close with a "Caveats & Next Steps" section when giving recommendations.
"""

DISCLAIMER = (
    "*This is educational information, not personalized investment advice. "
    "Consult a licensed advisor before acting. Past performance does not "
    "guarantee future results.*"
)


def format_persona(profile: dict | None) -> str:
    if not profile:
        return "(no profile set — ask user for goals/risk before personalized advice)"
    parts = [
        f"- Age: {profile.get('age', 'unspecified')}",
        f"- Risk tolerance: {profile.get('risk_tolerance', 'unspecified')}",
        f"- Annual income: {profile.get('income', 'unspecified')}",
        f"- Goals: {', '.join(profile.get('goals', [])) or 'unspecified'}",
        f"- Holdings: {profile.get('holdings', 'unspecified')}",
    ]
    return "\n".join(parts)


def format_page_facts(page_facts: dict | None) -> str:
    """Render page-visible numbers as a labelled block.

    Values are the exact numbers the user is looking at on their current
    page (projection, success prob, expected return, etc.). The LLM MUST
    prefer these over its own recomputation when the user asks about
    "this plan" or "these numbers".
    """
    if not page_facts:
        return ""
    lines = []
    for k, v in page_facts.items():
        if v in (None, "", [], {}):
            continue
        lines.append(f"- {k}: {v}")
    if not lines:
        return ""
    return "\n".join(lines)


def build_system_prompt(profile: dict | None, rag_block: str = "",
                          page_facts: dict | None = None) -> str:
    sys = SYSTEM_PROMPT.format(persona_block=format_persona(profile))
    pf = format_page_facts(page_facts)
    if pf:
        sys += (
            "\n\nPAGE FACTS (exact values the user is looking at right now — "
            "prefer these over recomputing; when the user says \"this plan\", "
            "\"my numbers\", or \"the projection\", they mean these):\n"
            f"{pf}"
        )
    if rag_block:
        sys += f"\n\nRELEVANT CONTEXT (use if helpful, cite when used):\n{rag_block}"
    return sys
