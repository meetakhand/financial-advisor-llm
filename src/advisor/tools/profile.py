"""User profile read/write — exposed as a tool so the agent can update it."""
from advisor.agent.memory import load_profile, save_profile


def get_user_profile(user_id: str) -> dict:
    return load_profile(user_id) or {"note": "no profile saved yet"}


def update_user_profile(user_id: str, updates: dict) -> dict:
    cur = load_profile(user_id) or {}
    cur.update(updates)
    save_profile(user_id, cur)
    return {"saved": True, "profile": cur}
