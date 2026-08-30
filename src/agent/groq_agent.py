"""Backward-compatibility shim — groq_agent now delegates to llm_agent.

Any code that imported run_groq_agent continues to work unchanged.
"""

from __future__ import annotations

from src.agent.llm_agent import run_llm_agent as run_groq_agent  # noqa: F401
from src.agent.analytical import SessionMemory  # noqa: F401

__all__ = ["run_groq_agent", "SessionMemory"]
