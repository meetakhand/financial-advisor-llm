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


def build_system_prompt(profile: dict | None, rag_block: str = "") -> str:
    sys = SYSTEM_PROMPT.format(persona_block=format_persona(profile))
    if rag_block:
        sys += f"\n\nRELEVANT CONTEXT (use if helpful, cite when used):\n{rag_block}"
    return sys
