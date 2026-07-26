# NexWealth MCP Server

Thin MCP adapter over the existing `src/advisor/*` pipeline. The Streamlit
app is untouched — this server only imports from `src/advisor/`.

## Install

```bash
pip install -r requirements.txt      # main advisor deps
pip install -r nexwealth_mcp/requirements.txt   # adds `mcp`
```

## Run standalone (smoke test)

```bash
cd /Users/apratapsingh/financial-advisor-llm
python -m nexwealth_mcp
```

The server speaks stdio MCP — no port. To poke it interactively:

```bash
npx @modelcontextprotocol/inspector python -m nexwealth_mcp
```

## Register with Claude Code

```bash
claude mcp add nexwealth \
  --scope user \
  --env HF_TOKEN=$HF_TOKEN \
  --env ALPHA_VANTAGE_KEY=$ALPHA_VANTAGE_KEY \
  --env CHROMA_DIR=~/financial-advisor-llm/data/chroma \
  -- bash -c "cd ~/financial-advisor-llm && python3 -m nexwealth_mcp"
```

Or edit `~/.claude.json` manually — see the skill README.

## Tools exposed

| Tool | Purpose |
|---|---|
| `list_customers` | Pick a customer to load |
| `get_customer` | Full record + holdings |
| `score_risk` | Tolerance + capacity → band |
| `narrate_risk` | Grounded LLM rationale |
| `plan_retirement` / `plan_education` / `plan_home` | Journey-specific plans |
| `analyze_portfolio` | Holdings + allocation |
| `run_benchmark` | Live 5Y CAGR vs peer ETF |
| `generate_recommendations` | 3 options + fit scores |
| `narrate_recommendation` | Grounded rec rationale |
| `run_pipeline` | Composite — one call runs the full 8-step chain |
| `get_last_committed_decision` | Prior HITL commit (baseline for reviews) |
| `get_hitl_log` | Full HITL history |
| `commit_hitl_decision` | Approve / Reject / Override |
| `build_report` | Markdown report, optionally save to disk |
| `search_finance_kb` | Hybrid RAG over the finance corpus |
