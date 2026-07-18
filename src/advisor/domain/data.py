"""SQLite persistence: customers, holdings, chat, HITL decision log.

Schema (Shape B for HITL — one row per pipeline run, updated in place):

    customers        one row per user profile
    holdings         one row per holding (ticker × units × cost basis × start_date)
    agent_runs       one row per pipeline invocation (metadata + JSON summary)
    hitl_log         one row per pipeline run: ai_suggested + final_choice + rationale

The chat panel state lives in Streamlit session_state, not the DB.

Database file: settings.chroma_dir's parent + 'profile.db'  (data/profile.db).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/profile.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id              TEXT UNIQUE,
    name                     TEXT NOT NULL,
    age                      INTEGER NOT NULL,
    annual_income            REAL NOT NULL,
    dependents               INTEGER NOT NULL DEFAULT 0,
    country                  TEXT DEFAULT 'US',
    currency                 TEXT DEFAULT 'USD',
    risk_answers_json        TEXT,
    primary_goal             TEXT,
    goal_inputs_json         TEXT,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS holdings (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id              INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    ticker                   TEXT NOT NULL,
    category                 TEXT,
    units                    REAL NOT NULL,
    buy_price                REAL NOT NULL,
    start_date               TEXT,
    UNIQUE (customer_id, ticker)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id              INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    journey                  TEXT NOT NULL,
    started_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agents_run_json          TEXT,
    summary_json             TEXT
);

-- Shape B: one row per pipeline run. Updated in place as the user reviews.
-- ``committed_at`` is set when the Report is emitted; before that the row is
-- an open review still awaiting a decision.
CREATE TABLE IF NOT EXISTS hitl_log (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id              INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    agent_run_id             INTEGER REFERENCES agent_runs(id) ON DELETE CASCADE,
    journey                  TEXT NOT NULL,
    run_timestamp            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ai_suggested             TEXT NOT NULL,
    final_choice             TEXT,              -- Moderate / Growth / Aggressive / custom
    final_action             TEXT,              -- approve / reject / override
    rationale                TEXT,
    override_json            TEXT,              -- custom allocation, if any
    committed_at             TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_holdings_customer  ON holdings(customer_id);
CREATE INDEX IF NOT EXISTS idx_runs_customer      ON agent_runs(customer_id);
CREATE INDEX IF NOT EXISTS idx_hitl_customer      ON hitl_log(customer_id);
CREATE INDEX IF NOT EXISTS idx_hitl_run           ON hitl_log(agent_run_id);
"""


@dataclass
class Holding:
    ticker: str
    category: str
    units: float
    buy_price: float
    start_date: str = ""

    def as_row(self) -> tuple:
        return (self.ticker, self.category, self.units, self.buy_price, self.start_date)


@dataclass
class Customer:
    id: int | None
    external_id: str
    name: str
    age: int
    annual_income: float
    dependents: int = 0
    country: str = "US"
    currency: str = "USD"
    risk_answers: list[int] = field(default_factory=list)
    primary_goal: str = ""
    goal_inputs: dict = field(default_factory=dict)
    holdings: list[Holding] = field(default_factory=list)


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript(_SCHEMA)


# --------------------- Customers ---------------------

def upsert_customer(customer: Customer) -> int:
    """Insert or update by external_id. Returns the customer id."""
    init_db()
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO customers
               (external_id, name, age, annual_income, dependents, country, currency,
                risk_answers_json, primary_goal, goal_inputs_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(external_id) DO UPDATE SET
                 name=excluded.name, age=excluded.age,
                 annual_income=excluded.annual_income, dependents=excluded.dependents,
                 country=excluded.country, currency=excluded.currency,
                 risk_answers_json=excluded.risk_answers_json,
                 primary_goal=excluded.primary_goal,
                 goal_inputs_json=excluded.goal_inputs_json
               RETURNING id""",
            (customer.external_id, customer.name, customer.age, customer.annual_income,
             customer.dependents, customer.country, customer.currency,
             json.dumps(customer.risk_answers), customer.primary_goal,
             json.dumps(customer.goal_inputs)),
        )
        cid = cur.fetchone()["id"]
        con.execute("DELETE FROM holdings WHERE customer_id = ?", (cid,))
        for h in customer.holdings:
            con.execute(
                """INSERT INTO holdings (customer_id, ticker, category, units, buy_price, start_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cid, *h.as_row()),
            )
        return cid


def _row_to_customer(con: sqlite3.Connection, row: sqlite3.Row) -> Customer:
    holdings = [
        Holding(ticker=h["ticker"], category=h["category"], units=h["units"],
                buy_price=h["buy_price"], start_date=h["start_date"] or "")
        for h in con.execute("SELECT * FROM holdings WHERE customer_id = ?", (row["id"],))
    ]
    return Customer(
        id=row["id"], external_id=row["external_id"], name=row["name"],
        age=row["age"], annual_income=row["annual_income"], dependents=row["dependents"],
        country=row["country"], currency=row["currency"],
        risk_answers=json.loads(row["risk_answers_json"] or "[]"),
        primary_goal=row["primary_goal"] or "",
        goal_inputs=json.loads(row["goal_inputs_json"] or "{}"),
        holdings=holdings,
    )


def get_customer(customer_id: int) -> Customer | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return _row_to_customer(con, row) if row else None


def get_customer_by_external(external_id: str) -> Customer | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM customers WHERE external_id = ?", (external_id,)
        ).fetchone()
        return _row_to_customer(con, row) if row else None


def list_customers() -> list[Customer]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM customers ORDER BY id").fetchall()
        return [_row_to_customer(con, r) for r in rows]


# --------------------- Agent runs ---------------------

def log_agent_run(customer_id: int, journey: str, agents_run: list[str],
                    summary: dict | None = None) -> int:
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO agent_runs (customer_id, journey, agents_run_json, summary_json)
               VALUES (?, ?, ?, ?) RETURNING id""",
            (customer_id, journey, json.dumps(agents_run),
             json.dumps(summary or {}, default=str)),
        )
        return cur.fetchone()["id"]


# --------------------- HITL (Shape B) ---------------------

def open_hitl_review(customer_id: int, agent_run_id: int, journey: str,
                      ai_suggested: str) -> int:
    """Insert an open HITL row (committed_at NULL). Returns the row id."""
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO hitl_log (customer_id, agent_run_id, journey, ai_suggested)
               VALUES (?, ?, ?, ?) RETURNING id""",
            (customer_id, agent_run_id, journey, ai_suggested),
        )
        return cur.fetchone()["id"]


def commit_hitl_decision(hitl_id: int, *, final_choice: str, final_action: str,
                          rationale: str = "",
                          override_allocation: dict | None = None) -> None:
    """Finalize the HITL row when the user approves/rejects/overrides."""
    if final_action not in {"approve", "reject", "override"}:
        raise ValueError(f"Bad final_action: {final_action}")
    override_json = json.dumps(override_allocation) if override_allocation else None
    with _conn() as con:
        con.execute(
            """UPDATE hitl_log
               SET final_choice = ?, final_action = ?, rationale = ?,
                   override_json = ?, committed_at = ?
               WHERE id = ?""",
            (final_choice, final_action, rationale, override_json,
             datetime.utcnow().isoformat(timespec="seconds"), hitl_id),
        )


def get_hitl_log(customer_id: int, *, only_committed: bool = True) -> list[dict]:
    query = "SELECT * FROM hitl_log WHERE customer_id = ?"
    if only_committed:
        query += " AND committed_at IS NOT NULL"
    query += " ORDER BY run_timestamp DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(query, (customer_id,))]


def latest_committed_for_journey(customer_id: int, journey: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            """SELECT * FROM hitl_log
               WHERE customer_id = ? AND journey = ? AND committed_at IS NOT NULL
               ORDER BY committed_at DESC LIMIT 1""",
            (customer_id, journey),
        ).fetchone()
        return dict(row) if row else None
