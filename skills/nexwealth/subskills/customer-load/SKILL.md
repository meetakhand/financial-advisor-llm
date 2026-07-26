---
name: nexwealth-customer-load
description: Load a customer into the RM session — pick one from the
  book and cache their profile in session state. Always the first
  sub-skill invoked in an RM conversation.
required_tools:
  - mcp__nexwealth__list_customers
  - mcp__nexwealth__get_customer
---

# Customer Load

## Workflow

### Step 1 — Identify the customer
If the RM already named a customer, skip to Step 2. Otherwise call
`mcp__nexwealth__list_customers` and present the list:

```
| # | External ID | Name | Age | Journey |
|---|---|---|---|---|
```

Wait for the RM to pick by number or name.

### Step 2 — Load full record
Call `mcp__nexwealth__get_customer(customer_id=<id>)`. Present a
one-line profile:

> **<Name>** — age <age>, income $<income>, <dependents> dependents,
> journey: <primary_goal>. <N> holdings on file.

### Step 3 — Populate session state
Set these in working memory:
- `current_customer_id` = <id>
- `current_customer_name` = <name>
- `current_journey` = <primary_goal or "Retirement Planning">

### Step 4 — Hand back to the router
Ask: *"What would you like to do — annual review, quick status,
rebalance, or answer a client question?"*
