"""Advisor Agent — grounded Financial Q&A via a ReAct-style tool loop.

Used when the intent classifier routes to "Financial Q&A". The turn runs
either as:

  - **ReAct loop** (default when LLM is available): the LLM is given a
    catalogue of tools (Alpha Vantage market data + deterministic financial
    calculators) plus retrieved RAG snippets. It Reasons, optionally emits a
    tool call, we Act by executing the tool, feed the Observation back, and
    the loop continues until the model returns a final assistant text (no
    tool_calls). Capped at ``MAX_REACT_STEPS`` iterations. Every tool call is
    captured so the UI can render an audit trail.

  - **Snippet-echo fallback**: used when ``LLM_PROVIDER=none``, ``HF_TOKEN``
    is empty, or the LLM turn errors after retries. Returns a legible answer
    built from the top-3 RAG snippets so the demo path always renders
    something.

Every returned answer flows through ``apply_guardrails`` — input screening +
directive scrub + disclaimer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from advisor.config import settings
from advisor.guardrails import apply_guardrails
from advisor.llm.prompts import build_system_prompt
from advisor.rag.retrieve import HybridRetriever, format_snippets
from advisor.tools.registry import DISPATCH, TOOLS


MAX_REACT_STEPS = 6      # Reason→Act→Observe iterations before we cap the loop
_TOOL_RESULT_TRUNC = 4000  # per-tool result payload cap when fed back to the LLM


@dataclass
class ToolCallRecord:
    name: str
    args: dict
    result_preview: str
    ok: bool
    error: str | None = None


@dataclass
class AdvisorAnswer:
    question: str
    answer_markdown: str
    citations: list[dict] = field(default_factory=list)  # {source, id, score}
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    follow_up: str | None = None
    was_blocked: bool = False
    provider: str = ""
    steps: int = 0             # ReAct iterations that ran (0 for snippet-echo)
    stopped_reason: str = ""   # "final_answer" | "max_steps" | "no_llm" | "llm_error"


_FOLLOW_UP_HINT = ("Want me to run this against your profile — projection numbers, "
                   "risk band, or a rebalancing plan?")


# ---------- ReAct scaffolding ------------------------------------------------

def _react_system_prompt(profile: dict | None, rag_block: str,
                            page_facts: dict | None) -> str:
    """System prompt tuned for tool-using turns.

    Wraps the standard ``build_system_prompt`` (which formats persona +
    PAGE FACTS + retrieval context) with ReAct-style instructions: think
    step-by-step, prefer tool calls over guesses, cite tools inline.
    """
    base = build_system_prompt(profile, rag_block, page_facts=page_facts)
    react_instructions = (
        "\n\nREACT LOOP\n"
        "- If a quantitative or live-market fact is needed, CALL A TOOL rather "
        "than guessing. Prefer tools over prose.\n"
        "- If PAGE FACTS above contain a number the user is asking about, "
        "USE THAT NUMBER — do not recompute it with a tool. Recompute only "
        "when the user is asking a *what-if* that changes an input.\n"
        "- For any journey plan recompute (e.g. \"what if I switch to "
        "Aggressive\"), call `plan_journey` with the risk_band the user "
        "asked about — do NOT use `retirement_projection` with a guessed "
        "annual_return.\n"
        "- Chain tool calls when necessary (e.g. get_stock_quote → "
        "get_company_overview → asset_allocation).\n"
        "- After each tool result, decide whether more tool calls are needed "
        "or whether you have enough to answer.\n"
        "- When you produce the final answer, include a [Tool: <name>] tag "
        "inline for every tool you used and a [Source: <name>] tag for every "
        "retrieved snippet you leaned on.\n"
        f"- You have at most {MAX_REACT_STEPS} tool-call rounds — plan "
        "accordingly.\n"
    )
    return base + react_instructions


def _dispatch_tool(name: str, args: dict) -> tuple[str, bool, str | None]:
    """Execute a tool call from the registry.

    Returns ``(result_json_str, ok, error)``. Result is JSON-serialised so
    the LLM sees a stable shape; we truncate large payloads so the context
    window doesn't blow up on news_sentiment / technical indicators.
    """
    fn = DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"}), False, "unknown_tool"
    try:
        raw = fn(**args) if args else fn()
    except TypeError as e:
        return json.dumps({"error": f"bad arguments: {e}"}), False, "bad_arguments"
    except Exception as e:  # noqa: BLE001 — tool errors are user-visible
        return json.dumps({"error": f"{type(e).__name__}: {e}"}), False, str(e)
    try:
        payload = json.dumps(raw, default=str)
    except (TypeError, ValueError):
        payload = json.dumps({"result": str(raw)})
    if len(payload) > _TOOL_RESULT_TRUNC:
        payload = payload[:_TOOL_RESULT_TRUNC] + "...<truncated>"
    return payload, True, None


def _parse_tool_args(raw: str | dict | None) -> dict:
    """Tool-call arguments come in as JSON strings from OpenAI-shaped APIs."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _preview_result(payload: str) -> str:
    """Short human-readable string for the UI audit trail."""
    if len(payload) <= 200:
        return payload
    return payload[:197] + "..."


def _run_react_loop(question: str, profile: dict | None,
                     snippets: list[dict],
                     page_facts: dict | None,
                     ) -> tuple[str, list[ToolCallRecord], int, str]:
    """Execute the Reason → Act → Observe loop.

    Returns (final_text, tool_call_records, steps_run, stopped_reason).
    Raises to the caller on transport-level LLM errors — the caller catches
    and falls back to the snippet-echo path.
    """
    from advisor.llm.client import chat

    system = _react_system_prompt(profile, format_snippets(snippets), page_facts)
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
    tool_calls_seen: list[ToolCallRecord] = []

    for step in range(1, MAX_REACT_STEPS + 1):
        resp = chat(messages, tools=TOOLS, temperature=0.2, max_tokens=800)
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            # No more tool use — this is the final assistant turn.
            return (msg.content or "").strip(), tool_calls_seen, step, "final_answer"

        # The assistant message that requested the tool calls must be kept
        # verbatim so the follow-up tool-role messages line up by tool_call_id.
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            name = tc.function.name
            args = _parse_tool_args(tc.function.arguments)
            payload, ok, err = _dispatch_tool(name, args)
            tool_calls_seen.append(ToolCallRecord(
                name=name, args=args,
                result_preview=_preview_result(payload),
                ok=ok, error=err,
            ))
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "name": name, "content": payload,
            })

    # Loop exhausted — ask the LLM once more to produce a final answer given
    # everything it has seen, but without offering more tool calls this time.
    messages.append({
        "role": "user",
        "content": (
            f"You've used {MAX_REACT_STEPS} tool-call rounds. Please produce "
            "the final answer now using what you have — no more tool calls."
        ),
    })
    resp = chat(messages, tools=None, temperature=0.2, max_tokens=800)
    final_text = (resp.choices[0].message.content or "").strip()
    return final_text, tool_calls_seen, MAX_REACT_STEPS, "max_steps"


# ---------- Fallback: snippet-echo -------------------------------------------

def _fallback_answer(question: str, snippets: list[dict]) -> str:
    if not snippets:
        return ("I don't have retrieved context that covers this question. Try "
                "rephrasing, or ask about retirement, education, or home-buying "
                "planning — I have grounded playbooks for those.")
    lines = [f"Based on the retrieved sources, here's what applies to *{question.strip()}*:", ""]
    for s in snippets[:3]:
        excerpt = s["text"].strip().replace("\n", " ")
        if len(excerpt) > 320:
            excerpt = excerpt[:317] + "..."
        lines.append(f"- {excerpt}  [Source: {s['source']}]")
    return "\n".join(lines)


# ---------- Public entry point -----------------------------------------------

def answer_question(question: str, profile: dict | None = None,
                     k: int = 6,
                     page_facts: dict | None = None) -> AdvisorAnswer:
    """Answer a free-text financial question with grounded retrieval + tools.

    profile is the persona block (age, risk, income, goals, holdings) that
    build_system_prompt understands. Pass None if no customer is active.
    page_facts is the labelled dict of numbers currently on the user's
    page (projection, success prob, expected return, funding gap, …). The
    LLM is instructed to prefer these over recomputation.
    """
    retriever = HybridRetriever()
    snippets = retriever.search(question, k=k)
    citations = [
        {"source": s["source"], "id": s["id"], "score": s["score"]}
        for s in snippets
    ]

    tool_calls_ref: list[ToolCallRecord] = []
    meta = {"steps": 0, "stopped_reason": ""}

    def _generate(_user_text: str) -> str:
        if settings.llm_provider == "none" or not settings.hf_token:
            meta["stopped_reason"] = "no_llm"
            return _fallback_answer(question, snippets)
        try:
            text, calls, steps, stopped = _run_react_loop(
                question, profile, snippets, page_facts,
            )
            tool_calls_ref.extend(calls)
            meta["steps"] = steps
            meta["stopped_reason"] = stopped
            # Empty LLM reply → fall back so the UI has something to render.
            if not text:
                meta["stopped_reason"] = "llm_error"
                return _fallback_answer(question, snippets)
            return text
        except Exception:
            meta["stopped_reason"] = "llm_error"
            return _fallback_answer(question, snippets)

    response, blocked = apply_guardrails(question, _generate)

    follow_up = None if blocked else _FOLLOW_UP_HINT
    return AdvisorAnswer(
        question=question,
        answer_markdown=response,
        citations=citations,
        tool_calls=tool_calls_ref,
        follow_up=follow_up,
        was_blocked=blocked,
        provider=("none" if settings.llm_provider == "none" else settings.llm_provider),
        steps=meta["steps"],
        stopped_reason=meta["stopped_reason"],
    )


__all__ = ["AdvisorAnswer", "ToolCallRecord", "answer_question", "MAX_REACT_STEPS"]
