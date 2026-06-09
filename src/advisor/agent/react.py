"""ReAct-style agent: RAG grounding + tool-calling loop."""
from __future__ import annotations

import json

from advisor.agent.safety import post_process
from advisor.llm.client import chat
from advisor.llm.prompts import build_system_prompt
from advisor.rag.retrieve import HybridRetriever, format_snippets
from advisor.tools.registry import DISPATCH, TOOLS

MAX_STEPS = 6
TOOL_OUTPUT_LIMIT = 4000  # chars; bound payloads to keep context small


def _serialize_tool_calls(tool_calls) -> list[dict]:
    out = []
    for tc in tool_calls:
        try:
            out.append(tc.model_dump())
        except AttributeError:
            out.append({
                "id": getattr(tc, "id", None),
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })
    return out


def _run_tool(name: str, args: dict) -> dict:
    fn = DISPATCH.get(name)
    if fn is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return fn(**args) if args else fn()
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def run(
    user_msg: str,
    history: list[dict],
    profile: dict | None,
    retriever: HybridRetriever | None = None,
    max_steps: int = MAX_STEPS,
) -> str:
    """Single turn: retrieve, build messages, loop until non-tool reply, post-process."""
    rag_block = ""
    if retriever is not None:
        snippets = retriever.search(user_msg, k=4)
        rag_block = format_snippets(snippets)

    sys = build_system_prompt(profile, rag_block)
    messages: list[dict] = [{"role": "system", "content": sys}, *history,
                            {"role": "user", "content": user_msg}]

    for _ in range(max_steps):
        resp = chat(messages, tools=TOOLS)
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            return post_process(msg.content or "")

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": _serialize_tool_calls(tool_calls),
        })
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _run_tool(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.function.name,
                "content": json.dumps(result, default=str)[:TOOL_OUTPUT_LIMIT],
            })

    return post_process(
        "I couldn't complete the analysis within the step budget. "
        "Try a narrower question or break it into parts."
    )
