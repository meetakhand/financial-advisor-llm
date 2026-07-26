---
name: nexwealth-annual-review
description: Run the full planning pipeline for the loaded customer,
  compare against last year's committed decision, and capture a fresh
  HITL commit. Also handles the "quick status" lite mode.
required_tools:
  - mcp__nexwealth__run_pipeline
  - mcp__nexwealth__get_last_committed_decision
  - mcp__nexwealth__commit_hitl_decision
  - mcp__nexwealth__build_report
---

# Annual Review

## Preconditions
- `current_customer_id` must be set. If not, invoke
  `nexwealth-customer-load` first.
- `current_journey` must be set (typically the customer's
  `primary_goal`).

## Workflow

### Step 1 — Fetch baseline
Call `mcp__nexwealth__get_last_committed_decision(customer_id, journey)`.

- **If a prior commit exists**: show `prior_model`, `committed_at`, and
  the `final_action`. This is the anchor for the delta.
- **If none**: note *"First review — no prior baseline."*

### Step 2 — Fresh pipeline run
Call `mcp__nexwealth__run_pipeline(customer_id, journey)`.

The response includes the full plan (`goal`, `portfolio`, `benchmark`,
`recommendation`, `rationale`, `risk`), the `hitl_id` for the open
review row, and any pipeline `warnings`. **Store `hitl_id` in session
state as `open_hitl_id`.**

If `warnings` is non-empty, print each verbatim before continuing.

### Step 3 — Present the delta
Render three blocks:

**Plan status**
```
| Metric | Last year | Today | Δ |
|---|---:|---:|---:|
| Funding ratio | <prior> | <goal.funding_ratio> | ±pp |
| Outlook | <prior> | <goal.outlook> | changed? |
| MC p10 / p50 / p90 | ... | ... | ... |
```

**Risk band** — mention only if it differs from the prior commit's
model band, or if `risk_rationale.source != "llm"` (surface the source).

**Portfolio drift**
```
| Asset class | Current % | Target % | Drift |
```
Target comes from `recommendation.options[<AI-suggested>].target_allocation_pct`.

### Step 4 — AI recommendation
List the three options from `recommendation.options` with fit scores.
Highlight the AI-suggested one (`recommendation.ai_suggested`). Print
the narrated rationale (`rationale.markdown`) verbatim.

If `rationale.source != "llm"`, add a one-line badge: *"Rationale
generated from deterministic template — LLM narration unavailable."*

### Step 5 — HITL commit
Ask the RM: **Approve / Reject / Override?**

Do not proceed to Step 6 until the RM answers explicitly.

- **Approve** → `commit_hitl_decision(hitl_id=<open_hitl_id>, final_action="approve", final_choice=<ai_suggested>)`
- **Reject** → ask for one-line rationale, then
  `commit_hitl_decision(..., final_action="reject", final_choice=<ai_suggested>, rationale=<...>)`
- **Override** → ask which model *or* custom allocation, and rationale.
  If a model: `commit_hitl_decision(..., final_action="override", final_choice=<model>, rationale=<...>)`.
  If custom allocation: pass `override_allocation` as a
  `{asset_class: pct}` dict summing to 100.

Do not proceed until the commit tool returns `{"committed": true}`.

### Step 6 — Client packet
Ask: *"Save the report locally, or just show it?"*

- Save: `build_report(customer_id, journey, save_to="/Users/<user>/nexwealth-reports/<external_id>-<journey>-<YYYY-MM-DD>.md")`
- Show only: `build_report(customer_id, journey)` and paste the returned
  markdown into the chat.

## Lite mode (quick status)

Triggered when the RM says "quick check" / "status" / "how is X doing".

Skip Steps 5-6. Present only:
- Step 1 baseline
- Step 2 pipeline run (`allow_live_prices=false` for speed)
- Step 3 delta table
- A one-line summary: *"<Name>'s <journey> is <outlook>, funding
  ratio <X%>. No commit needed — this is a status check."*
