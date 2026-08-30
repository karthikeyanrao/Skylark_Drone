"""Provider-agnostic LLM agent — works with any OpenAI-compatible endpoint.

Default provider: Google Gemini Flash (free at aistudio.google.com, no credit card).
Alternate providers supported via env vars LLM_BASE_URL + LLM_MODEL:
  - Cerebras:  https://api.cerebras.ai/v1          llama3.1-8b
  - Groq:      https://api.groq.com/openai/v1      llama-3.3-70b-versatile

Falls back to the deterministic analytical agent if LLM_API_KEY is not set.
"""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from src.agent.analytical import SessionMemory, run_analytical_agent
from src.agent.system_prompt import SYSTEM_PROMPT
from src.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from src.tools.query_tools import TOOL_DEFINITIONS, dispatch_tool


def _openai_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in TOOL_DEFINITIONS
    ]


def run_llm_agent(user_message: str, memory: SessionMemory, history: list[dict]) -> str:
    """Run the LLM agent.  Falls back gracefully if no API key is configured."""
    if not LLM_API_KEY:
        return (
            "**AI agent mode requires a free API key.**\n\n"
            "Get one in under 2 minutes — no credit card needed:\n"
            "- **Google Gemini** (recommended): [aistudio.google.com](https://aistudio.google.com) "
            "→ *Get API key* → set `LLM_API_KEY` in your `.env`\n"
            "- **Cerebras**: [console.cerebras.ai](https://console.cerebras.ai) "
            "→ set `LLM_API_KEY` + `LLM_BASE_URL=https://api.cerebras.ai/v1` + `LLM_MODEL=llama3.1-8b`\n\n"
            "---\n*Falling back to analytical agent:*\n\n"
            + run_analytical_agent(user_message, memory)
        )

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    mem_note = memory.to_dict()
    if any(v for v in mem_note.values() if v):
        messages.append({"role": "system", "content": f"Session memory: {json.dumps(mem_note)}"})

    for msg in history[-10:]:
        messages.append(msg)

    messages.append({"role": "user", "content": user_message})

    tools = _openai_tools()

    try:
        for _ in range(5):
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
                tool_choice="auto",
                max_tokens=2048,
            )
            choice = response.choices[0]

            # Gemini returns tool_calls=None not [] when there are none
            tool_calls = choice.message.tool_calls or []

            # Append assistant turn — use model_dump() to serialise correctly
            messages.append(choice.message.model_dump(exclude_none=True))

            if not tool_calls:
                return choice.message.content or "No response generated."

            for tc in tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = dispatch_tool(tc.function.name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str),
                    }
                )

        return "I couldn't complete the analysis within the tool-call limit. Please try a narrower question."
    except Exception as exc:
        return (
            f"⚠️ **LLM Error** (`{exc}`)\n\n"
            "*Falling back to analytical agent:*\n\n"
            + run_analytical_agent(user_message, memory)
        )
