---
name: nexwealth-meeting-prep
description: Package the current customer's report + talking points
  before an RM meeting.
required_tools:
  - mcp__nexwealth__build_report
  - mcp__nexwealth__get_hitl_log
  - mcp__nexwealth__search_finance_kb
---

# Meeting Prep

## Preconditions
`current_customer_id` and `current_journey` must be set.

## Workflow

### Step 1 — Regenerate report
Call `mcp__nexwealth__build_report(customer_id, journey, save_to=...)`
with a dated filename under `~/nexwealth-reports/`.

### Step 2 — HITL history
Call `mcp__nexwealth__get_hitl_log(customer_id, only_committed=true)`.
Present the last 3 commits as a compact table — this is the "what
have we agreed to over time" view the RM will walk through.

### Step 3 — Talking-point bullets
Compose 3-5 bullets that the RM can read out. Ground each bullet in a
specific number from the report (funding ratio, MC band, benchmark
excess return, portfolio drift). Do not editorialize beyond the
numbers.

### Step 4 — Anticipated questions
Ask the RM: *"Any specific client concerns to prep answers for?"* If
they name a topic (e.g. "tax on rebalancing"), call
`mcp__nexwealth__search_finance_kb(query=<topic>)` and prepare a
2-sentence, cited answer.

### Step 5 — Final packet
Confirm: report path, top talking points, and any KB answers pulled.
Hand back to the router.
