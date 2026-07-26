---
name: nexwealth-rebalance-decision
description: Standalone HITL commit path for rebalance decisions
  when the RM already has a pipeline result in session and just
  needs to approve, reject, or override.
required_tools:
  - mcp__nexwealth__generate_recommendations
  - mcp__nexwealth__narrate_recommendation
  - mcp__nexwealth__commit_hitl_decision
---

# Rebalance Decision

## When to use
- The RM has already reviewed the plan and just wants to record a
  fresh Approve/Reject/Override without re-running the full pipeline.
- `open_hitl_id` must be in session state. If not, invoke
  `nexwealth-annual-review` instead — you need a fresh HITL row.

## Workflow

### Step 1 — Show current AI suggestion
If not already presented this turn, call
`mcp__nexwealth__generate_recommendations(customer_id)` and
`mcp__nexwealth__narrate_recommendation(customer_id)`. Show the three
options + narrated rationale.

### Step 2 — Confirm the action
Ask **Approve / Reject / Override** and wait. Never assume.

### Step 3 — Commit
Same commit rules as annual-review Step 5. Do not proceed until the
commit tool returns success.

### Step 4 — Confirm to RM
Read back: *"Committed. HITL row #<id>: <action> — <choice>. Rationale
on file."*
