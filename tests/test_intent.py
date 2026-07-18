"""Intent classifier — keyword-only path (LLM disabled)."""
import os

os.environ["LLM_PROVIDER"] = "none"   # keyword-only path

from advisor.agents.intent import (
    JOURNEYS, OUT_OF_SCOPE, OUT_OF_SCOPE_MESSAGE, classify_intent,
)


def test_retirement_hit():
    r = classify_intent("Am I on track for retirement at 60?")
    assert r.journey == "Retirement Planning"
    assert r.source in ("keyword", "llm+keyword")


def test_401k_alias():
    r = classify_intent("How much can I contribute to my 401(k) this year?")
    assert r.journey == "Retirement Planning"


def test_child_education_hit():
    r = classify_intent("Saving for my daughter's college in 12 years")
    assert r.journey == "Child Education"


def test_529_alias():
    r = classify_intent("What's a 529 plan?")
    assert r.journey == "Child Education"


def test_buy_home_hit():
    r = classify_intent("I want to buy a house in 2029, need to save down payment")
    assert r.journey == "Buy Home"


def test_qa_fallback():
    r = classify_intent("What is a mutual fund vs an ETF?")
    assert r.journey == "Financial Q&A"


def test_empty_defaults_to_out_of_scope():
    r = classify_intent("")
    assert r.journey == OUT_OF_SCOPE
    assert r.source == "default"


def test_output_is_one_of_journeys():
    for q in ["some random text", "retirement question", "kid tuition", "buying my first condo"]:
        r = classify_intent(q)
        assert r.journey in JOURNEYS


def test_non_financial_question_is_out_of_scope():
    for q in [
        "What's the weather like tomorrow?",
        "Give me a recipe for pancakes",
        "Write me a poem about cats",
        "Who won the World Cup in 2022?",
        "Translate this to French: hello world",
    ]:
        r = classify_intent(q)
        assert r.journey == OUT_OF_SCOPE, f"Expected Out of Scope for {q!r}, got {r.journey!r}"


def test_generic_finance_question_stays_financial_qa():
    for q in [
        "Should I pay down my credit card debt or invest?",
        "What is dollar-cost averaging?",
        "How does inflation affect my savings account?",
        "Explain the difference between a stock and a bond",
    ]:
        r = classify_intent(q)
        assert r.journey == "Financial Q&A", f"Expected Financial Q&A for {q!r}, got {r.journey!r}"


def test_out_of_scope_message_shape():
    # Chat surfaces render this string verbatim — make sure it stays reasonable.
    lower = OUT_OF_SCOPE_MESSAGE.lower()
    assert "not something i can help with" in lower
    assert "retirement" in lower
