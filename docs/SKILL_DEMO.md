# NexWealth AI — Skill + MCP Demo (One-Pager)

*RM-facing demonstration of the same pipeline that powers the Streamlit
app, now driven conversationally through a Claude Skill with a local
MCP server. The Streamlit app is unchanged — this is the "product
evolution" prototype.*

---

## Prerequisites (5 min, one-time)

| # | Step | Command / action |
|---|---|---|
| 1 | Have the repo cloned at `/Users/apratapsingh/financial-advisor-llm/` with `.env` populated (`HF_TOKEN`, `ALPHA_VANTAGE_KEY`). | — |
| 2 | Install the main advisor deps + MCP SDK. | `cd /Users/apratapsingh/financial-advisor-llm && pip install -r requirements.txt && pip install -r nexwealth_mcp/requirements.txt` |
| 3 | Confirm the RAG index and SQLite are populated (run once if fresh). | `python scripts/build_rag_index.py && python -c "from advisor.domain.data import init_db; init_db()"` |
| 4 | Smoke-test the MCP server end-to-end. | `npx @modelcontextprotocol/inspector python -m nexwealth_mcp` → click a tool, verify JSON comes back. |
| 5 | Install Claude Code and confirm `claude` is on `$PATH`. | `claude --version` |

---

## Setup (2 min)

### A. Register the MCP server with Claude Code

```bash
claude mcp add nexwealth \
  --scope user \
  --env HF_TOKEN=$HF_TOKEN \
  --env ALPHA_VANTAGE_KEY=$ALPHA_VANTAGE_KEY \
  --env CHROMA_DIR=/Users/apratapsingh/financial-advisor-llm/data/chroma \
  -- bash -c "cd /Users/apratapsingh/financial-advisor-llm && python3 -m nexwealth_mcp"
```

Note: the `--` separates Claude Code's flags from the command. The
`bash -c` wrapper is needed so the server starts *inside* the repo,
which is how `nexwealth_mcp/server.py` finds `src/advisor/*` on its
Python path.

Verify: `claude mcp list` shows `nexwealth: ... ✓ Connected`. In an
interactive session, `/mcp` should list ~15 `mcp__nexwealth__*` tools.

### B. Install the skill bundle

```bash
mkdir -p ~/.claude/skills
ln -sf /Users/apratapsingh/financial-advisor-llm/skills/nexwealth \
       ~/.claude/skills/nexwealth
```

Verify: in Claude Code, `/skills` lists `nexwealth` and the five
sub-skills (`nexwealth-customer-load`, `nexwealth-annual-review`,
`nexwealth-ask-kb`, `nexwealth-rebalance-decision`,
`nexwealth-meeting-prep`).

**Note on lazy loading:** only the router `SKILL.md` (~200 tokens) is
pulled into every conversation. Sub-skills load only when their
trigger fires — the RM's context never bloats with tools they aren't
using in the current step.

---

## Demo Script (90 seconds, live)

Open Claude Code. Say the line in **bold**; the model runs the tool
calls shown underneath.

### 1. Load customer
> **RM: `/nexwealth` Pull up Priya Sharma.**

Claude → `nexwealth-customer-load` sub-skill loads →
`mcp__nexwealth__list_customers` → `mcp__nexwealth__get_customer(3)`
→ prints:
> *Priya Sharma — age 42, income $145k, 2 dependents, journey:
> Retirement Planning. 6 holdings on file. What would you like to do?*

### 2. Run the annual review
> **RM: Run her annual review.**

Claude → `nexwealth-annual-review` loads →
- `mcp__nexwealth__get_last_committed_decision(3, "Retirement Planning")`
  → *"Prior commit 2025-07-15: Growth model approved, funding ratio 74%."*
- `mcp__nexwealth__run_pipeline(3, "Retirement Planning")`
  → returns full plan + `hitl_id=427`
- Prints the delta table (funding 74% → 79%, +5pp; outlook Uncertain →
  Uncertain; portfolio drift equities 70% → 74%)
- Prints the 3 options + grounded rationale

### 3. Human-in-the-loop
> **RM: Override — trim equities, move to Moderate. She's nervous
> about 2026 volatility.**

Claude → `mcp__nexwealth__commit_hitl_decision(hitl_id=427,
final_action="override", final_choice="Moderate", rationale="RM
trimmed equities after 4pp drift; client nervous about 2026
volatility.")`
→ *"Committed. HITL row #427 updated."*

### 4. Follow-up question — RAG path
> **RM: Also, she asked if 401(k) limits changed this year.**

Claude → `nexwealth-annual-review` unloads, `nexwealth-ask-kb` loads →
`mcp__nexwealth__search_finance_kb(query="401k contribution limit
2026", k=5)` →
> *"IRS Notice 2025-XX: 2026 employee deferral limit is $24,500
> ($31,500 with catch-up if 50+). [source: IRS Notice 2025-XX]"*

### 5. Report export
> **RM: Save her packet for the 3pm meeting.**

Claude → `nexwealth-meeting-prep` loads →
`mcp__nexwealth__build_report(3, "Retirement Planning",
save_to="~/nexwealth-reports/CUST-003-Retirement-2026-07-26.md")` →
`mcp__nexwealth__get_hitl_log(3, only_committed=true)` →
prints 3 talking-point bullets grounded in the report numbers.

---

## What to point at during the demo

1. **The tool-call trace is the audit trail.** Every number the RM
   sees came from a visible MCP call — nothing is hallucinated. Show
   the Claude Code trace panel.
2. **Sub-skill loading is visible.** When the topic shifts from
   annual-review to KB, only the KB skill's tool (`search_finance_kb`)
   is in scope. Small context per step.
3. **Same pipeline as the Streamlit app.** Open the Streamlit app in
   another tab (`streamlit run app/0_Home.py`), pull up Priya's HITL
   log — row #427 is there, exactly as committed via MCP. The two
   surfaces share the same SQLite.
4. **RAG citations are real.** Click through the snippet path to
   `corpus/irs/...` — it's the actual primary source, not paraphrased.
5. **Nothing was invented for the demo.** Every MCP tool wraps
   existing agent code in 5-8 lines. The advisor package didn't
   change.

---

## Fallback if something breaks live

| Symptom | Fast fix |
|---|---|
| `claude mcp list` shows `nexwealth` as `disconnected` | Check `python -m nexwealth_mcp` runs standalone; usually a missing env var. |
| Alpha Vantage throttled → benchmark warns "illustrative" | Expected — the demo still works, just show the warning surfaced by the skill. |
| `search_finance_kb` returns `[]` | Run `python scripts/build_rag_index.py` — index isn't built yet. |
| Sub-skill doesn't trigger from RM's phrasing | Fall back to explicit invocation: `/nexwealth-annual-review`. |
| HuggingFace 401 / 429 | The skill prints the fallback banner from the LLM client — this is the same behavior as the Streamlit app; call it out as a designed-in guardrail. |

---

## What this delivery proves

- **The pipeline is reusable.** Same agent code powers Streamlit *and*
  a conversational RM interface with no core changes.
- **Nested skills keep the context lean.** Router ≈ 200 tokens; only
  the active sub-skill's tools are loaded.
- **MCP is the right seam.** Business logic stays server-side (with
  guardrails and HITL SQLite intact); the client is just the driver.
- **This is the product path.** The Streamlit app is the capstone
  submission; the Skill + MCP bundle is the productized RM tool once
  conversational LLMs become the primary interface.
