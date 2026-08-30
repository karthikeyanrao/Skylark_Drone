"""Load deals and work orders from monday.com (live) or local Excel (pytest only)."""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd

from src.cleaning.deals import clean_deals
from src.cleaning.quality_report import QualityReport
from src.cleaning.work_orders import clean_work_orders
from src.config import (
    DEALS_BOARD_ID,
    DEALS_EXCEL,
    WORK_ORDERS_BOARD_ID,
    WORK_ORDERS_EXCEL,
    monday_setup_missing,
    use_monday_api,
)
from src.monday_client import MondayClient, MondayClientError

logger = logging.getLogger(__name__)

_deals_cache: pd.DataFrame | None = None
_work_orders_cache: pd.DataFrame | None = None
_deals_report: QualityReport | None = None
_wo_report: QualityReport | None = None


def _items_to_dataframe(items: list[dict[str, Any]], columns_map: dict[str, str]) -> pd.DataFrame:
    rows = []
    for item in items:
        name_val = item.get("name")
        row: dict[str, Any] = {
            "Deal Name": name_val,
            "Deal name masked": name_val,
            "Name": name_val,
        }
        col_by_id = {cv["id"]: cv for cv in item.get("column_values", [])}
        for col_id, col_title in columns_map.items():
            if col_id == "name":
                continue
            cv = col_by_id.get(col_id, {})
            row[col_title] = cv.get("text") or None
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=list(columns_map.values()))
    return pd.DataFrame(rows)


def _load_from_monday(board_id: str) -> pd.DataFrame:
    client = MondayClient()
    items = client.get_board_items(board_id)
    columns = client.get_board_columns(board_id)
    col_map = {c["id"]: c["title"] for c in columns}
    return _items_to_dataframe(items, col_map)


def _pytest_running() -> bool:
    """True when invoked from a pytest session (allows Excel fallback for fixtures)."""
    return os.getenv("PYTEST_RUNNING", "").strip().lower() in ("1", "true", "yes")


def _load_deals_raw() -> pd.DataFrame:
    if use_monday_api():
        try:
            return _load_from_monday(DEALS_BOARD_ID)
        except MondayClientError as exc:
            logger.error("monday.com deals fetch failed: %s", exc)
            raise

    # Excel path — only permitted in pytest to keep the cleaning tests offline
    if _pytest_running():
        logger.info("PYTEST_RUNNING: loading deals from local Excel fixture")
        return pd.read_excel(DEALS_EXCEL)

    # Reach here only when board IDs are missing in a live run
    raise RuntimeError(
        "monday.com board IDs are not configured. "
        "Set DEALS_BOARD_ID and WORK_ORDERS_BOARD_ID in .env (or Streamlit Cloud secrets) "
        "then refresh the app."
    )


def _load_work_orders_raw() -> pd.DataFrame:
    if use_monday_api():
        try:
            return _load_from_monday(WORK_ORDERS_BOARD_ID)
        except MondayClientError as exc:
            logger.error("monday.com work orders fetch failed: %s", exc)
            raise

    if _pytest_running():
        logger.info("PYTEST_RUNNING: loading work orders from local Excel fixture")
        return pd.read_excel(WORK_ORDERS_EXCEL, header=1)

    raise RuntimeError(
        "monday.com board IDs are not configured. "
        "Set DEALS_BOARD_ID and WORK_ORDERS_BOARD_ID in .env (or Streamlit Cloud secrets) "
        "then refresh the app."
    )


def get_deals(refresh: bool = False) -> tuple[pd.DataFrame, QualityReport]:
    global _deals_cache, _deals_report
    if _deals_cache is None or refresh:
        raw = _load_deals_raw()
        _deals_cache, _deals_report = clean_deals(raw)
    return _deals_cache.copy(), _deals_report  # type: ignore[return-value]


def get_work_orders(refresh: bool = False) -> tuple[pd.DataFrame, QualityReport]:
    global _work_orders_cache, _wo_report
    if _work_orders_cache is None or refresh:
        raw = _load_work_orders_raw()
        _work_orders_cache, _wo_report = clean_work_orders(raw)
    return _work_orders_cache.copy(), _wo_report  # type: ignore[return-value]


def data_source_label() -> str:
    if use_monday_api():
        return "monday.com (live)"
    if monday_setup_missing():
        return "⚠️ monday.com — board IDs not set"
    return "local Excel (pytest fixture)"
