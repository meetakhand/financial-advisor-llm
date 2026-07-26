---
name: nexwealth-ask-kb
description: Answer a general financial question by citing the RAG
  corpus (SEC / IRS / FINRA / glossary). Never uses pre-training
  knowledge for regulatory figures.
required_tools:
  - mcp__nexwealth__search_finance_kb
---

# Ask Knowledge Base

## When to use
- RM passes through a client question about regulations, definitions,
  or figures ("what's the 2026 Roth limit", "explain a backdoor Roth").
- RM wants a definition for their own reference.

## Workflow

### Step 1 — Retrieve
Call `mcp__nexwealth__search_finance_kb(query=<full question>, k=5)`.

### Step 2 — Answer with citations
- If snippets are returned, compose an answer of at most 4 sentences,
  quoting or paraphrasing the snippets and citing every specific
  figure with the `source` field from the retriever.
- If **no** snippets come back, say so explicitly: *"The finance corpus
  didn't return a match. I won't guess a regulatory number — check
  the source directly."* Do not fall back to pre-training knowledge.

### Step 3 — Offer follow-up
Ask if the RM wants to loop the answer back into the current
customer's plan (e.g., recompute retirement with the new contribution
limit). If yes, hand back to `nexwealth-annual-review`.
