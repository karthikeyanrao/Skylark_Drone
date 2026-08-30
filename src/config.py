"""Application configuration — monday.com + LLM first defaults."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DEALS_EXCEL = ROOT_DIR / "Deal funnel Data.xlsx"
WORK_ORDERS_EXCEL = ROOT_DIR / "Work_Order_Tracker Data.xlsx"

# ── LLM (any OpenAI-compatible provider) ─────────────────────────────────────
# Default: Google Gemini Flash — free at aistudio.google.com, no credit card.
# Switch to Cerebras: LLM_BASE_URL=https://api.cerebras.ai/v1  LLM_MODEL=llama3.1-8b
# Switch to Groq:     LLM_BASE_URL=https://api.groq.com/openai/v1  LLM_MODEL=llama-3.3-70b-versatile
AGENT_MODE = os.getenv("AGENT_MODE", "llm").lower()  # llm | analytical
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
)
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")

# Legacy Groq compat — if only GROQ_API_KEY is set, promote it to the LLM slot
_groq_key = os.getenv("GROQ_API_KEY", "")
if _groq_key and not LLM_API_KEY:
    LLM_API_KEY = _groq_key
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))

# ── Data source ───────────────────────────────────────────────────────────────
# Default: monday.com live boards (required by assignment).
# Excel fallback is ONLY for pytest (PYTEST_RUNNING=1) — never for the hosted demo.
DATA_SOURCE = os.getenv("DATA_SOURCE", "monday").lower()
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN", "")
DEALS_BOARD_ID = os.getenv("DEALS_BOARD_ID", "")
WORK_ORDERS_BOARD_ID = os.getenv("WORK_ORDERS_BOARD_ID", "")
MONDAY_API_VERSION = os.getenv("MONDAY_API_VERSION", "2024-10")

# ── Domain constants ──────────────────────────────────────────────────────────
CANONICAL_SECTORS = frozenset(
    {"Mining", "Renewables", "Railways", "Powerline", "Construction", "Others"}
)

WON_STAGES = frozenset(
    {"G. Project Won", "H. Work Order Received", "J. Invoice sent", "K. Amount Accrued"}
)
LOST_STAGES = frozenset({"L. Project Lost", "O. Not Relevant at all"})

# ── Brand colours (white + orange, no gradients) ──────────────────────────────
BRAND_ORANGE = "#FF6B00"
BRAND_ORANGE_DARK = "#E05E00"
BRAND_WHITE = "#FFFFFF"
BRAND_BG = "#FFF8F3"
BRAND_TEXT = "#1A1A1A"
BRAND_BORDER = "#FFD4B8"


def use_monday_api() -> bool:
    """True when all three monday.com credentials are present and DATA_SOURCE=monday."""
    if DATA_SOURCE != "monday":
        return False
    return bool(MONDAY_API_TOKEN and DEALS_BOARD_ID and WORK_ORDERS_BOARD_ID)


def monday_setup_missing() -> bool:
    """True when DATA_SOURCE=monday but board IDs are not yet configured."""
    return DATA_SOURCE == "monday" and not (DEALS_BOARD_ID and WORK_ORDERS_BOARD_ID)


def use_llm_agent() -> bool:
    """True when an LLM API key is available and AGENT_MODE=llm."""
    return AGENT_MODE == "llm" and bool(LLM_API_KEY)


# ---------------------------------------------------------------------------
# Backward-compat shim — code that imported use_groq_agent still works
# ---------------------------------------------------------------------------
def use_groq_agent() -> bool:  # noqa: D401
    """Deprecated alias for use_llm_agent()."""
    return use_llm_agent()
