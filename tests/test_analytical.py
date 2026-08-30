"""Tests for analytical agent routing and revenue clarification."""

from __future__ import annotations

from src.agent.analytical import SessionMemory, run_analytical_agent


def test_revenue_clarification_then_billed_answer():
    memory = SessionMemory()
    first = run_analytical_agent("What's our revenue this quarter?", memory)
    assert "Quick clarification" in first
    assert memory.revenue_definition is None

    second = run_analytical_agent("billed value", memory)
    assert "Quick clarification" not in second
    assert memory.revenue_definition == "billed"
    assert "Billed" in second


def test_billed_value_skips_clarification_on_first_message():
    memory = SessionMemory()
    response = run_analytical_agent("billed value this quarter", memory)
    assert "Quick clarification" not in response
    assert memory.revenue_definition == "billed"
    assert "Billed" in response


def test_this_and_last_quarter_billed():
    memory = SessionMemory()
    response = run_analytical_agent("billed value this and last quarter", memory)
    assert "this calendar quarter" in response.lower()
    assert "last calendar quarter" in response.lower()
    assert "Last invoice date" in response
