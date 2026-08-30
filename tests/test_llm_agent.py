"""Tests for LLM agent fallback and tool schema generation."""

from __future__ import annotations

from src.agent.analytical import SessionMemory
from src.agent.llm_agent import _openai_tools, run_llm_agent


def test_openai_tools_schema_structure():
    tools = _openai_tools()
    assert len(tools) >= 3
    tool_names = [t["function"]["name"] for t in tools]
    assert "query_deals" in tool_names
    assert "query_work_orders" in tool_names
    assert "join_deals_to_work_orders" in tool_names


def test_llm_agent_fallback_when_no_api_key(monkeypatch):
    monkeypatch.setattr("src.agent.llm_agent.LLM_API_KEY", "")
    memory = SessionMemory()
    res = run_llm_agent("How many deals have we won?", memory, [])
    assert "analytical agent" in res.lower()
