"""Server-side query tools — aggregation in pandas, not in the LLM."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from rapidfuzz import fuzz, process

from src.cleaning.canonical import (
    DEALS_COLUMNS,
    STATUS_COLUMN_DESCRIPTIONS,
    WORK_ORDERS_COLUMNS,
)
from src.cleaning.quality_report import QualityReport
from src.data.loader import get_deals, get_work_orders


def get_board_schema() -> dict[str, Any]:
    return {
        "deals": {
            "columns": DEALS_COLUMNS,
            "notes": {
                "Closure Probability": "Categorical (High/Medium/Low) — never sum or average as a number.",
                "Sector/service": "Canonical set: Mining, Renewables, Railways, Powerline, Construction, Others.",
            },
        },
        "work_orders": {
            "columns": WORK_ORDERS_COLUMNS,
            "status_columns": STATUS_COLUMN_DESCRIPTIONS,
        },
    }


def _apply_date_range(df: pd.DataFrame, col: str, date_range: dict | None) -> pd.DataFrame:
    if not date_range or col not in df.columns:
        return df
    out = df.copy()
    start = date_range.get("start")
    end = date_range.get("end")
    if start:
        out = out[out[col] >= pd.Timestamp(start)]
    if end:
        out = out[out[col] <= pd.Timestamp(end)]
    return out


def _current_quarter_range() -> tuple[pd.Timestamp, pd.Timestamp]:
    now = pd.Timestamp.now()
    q = (now.month - 1) // 3
    start = pd.Timestamp(year=now.year, month=q * 3 + 1, day=1)
    if q == 3:
        end = pd.Timestamp(year=now.year + 1, month=1, day=1) - pd.Timedelta(days=1)
    else:
        end = pd.Timestamp(year=now.year, month=(q + 1) * 3 + 1, day=1) - pd.Timedelta(days=1)
    return start, end


def query_deals(
    sector: str | None = None,
    stage: str | None = None,
    status: str | None = None,
    date_range: dict | None = None,
    date_column: str = "Tentative Close Date",
    group_by: str | None = None,
    metric: str = "count",
    value_column: str = "Masked Deal value",
) -> dict[str, Any]:
    df, base_report = get_deals()
    report = QualityReport(board="Deals", rows_in=len(df))
    report.rows_dropped = base_report.rows_dropped
    report.flags = list(base_report.flags)
    report.cross_check_mismatches = list(base_report.cross_check_mismatches)

    # Normalize if LLM passes list instead of string
    if isinstance(sector, list):
        sector = sector[0] if sector else None
    if isinstance(stage, list):
        stage = stage[0] if stage else None
    if isinstance(status, list):
        status = status[0] if status else None
    if isinstance(group_by, list):
        group_by = group_by[0] if group_by else None

    if sector:
        df = df[df["Sector/service"].astype(str).str.lower() == str(sector).lower()]
    if stage:
        df = df[df["Deal Stage"].astype(str).str.contains(str(stage), case=False, na=False)]
    if status:
        df = df[df["Deal Status"].astype(str).str.lower() == str(status).lower()]
    df = _apply_date_range(df, date_column, date_range)

    result: dict[str, Any]
    if group_by and group_by in df.columns:
        grouped = df.groupby(df[group_by].fillna("Unknown"), dropna=False)
        if metric == "sum":
            result = grouped[value_column].sum(min_count=1).fillna(0).to_dict()
        else:
            result = grouped.size().to_dict()
    else:
        if metric == "sum":
            result = {"total": float(df[value_column].sum(min_count=1) or 0), "count": len(df)}
        else:
            result = {"count": len(df)}

    report.rows_out = len(df)
    report.add_completeness(df, [group_by or "Deal Status", value_column, date_column])
    return {"data": result, "rows": len(df), "quality_report": report.to_dict()}


def query_work_orders(
    sector: str | None = None,
    status: str | None = None,
    status_column: str = "Execution Status",
    date_range: dict | None = None,
    date_column: str = "Data Delivery Date",
    group_by: str | None = None,
    metric: str = "count",
    value_column: str = "Billed Value in Rupees (Incl of GST.) (Masked)",
) -> dict[str, Any]:
    df, base_report = get_work_orders()
    report = QualityReport(board="Work Orders", rows_in=len(df))
    report.flags = list(base_report.flags)
    report.null_causes = dict(base_report.null_causes)

    if isinstance(sector, list):
        sector = sector[0] if sector else None
    if isinstance(status, list):
        status = status[0] if status else None
    if isinstance(status_column, list):
        status_column = status_column[0] if status_column else "Execution Status"
    if isinstance(group_by, list):
        group_by = group_by[0] if group_by else None

    if sector:
        df = df[df["Sector"].astype(str).str.lower() == str(sector).lower()]
    if status and status_column in df.columns:
        df = df[df[status_column].astype(str).str.lower() == str(status).lower()]
    df = _apply_date_range(df, date_column, date_range)

    if group_by and group_by in df.columns:
        grouped = df.groupby(df[group_by].fillna("Unknown"), dropna=False)
        if metric == "sum":
            result = grouped[value_column].sum(min_count=1).fillna(0).to_dict()
        else:
            result = grouped.size().to_dict()
    else:
        if metric == "sum":
            result = {"total": float(df[value_column].sum(min_count=1) or 0), "count": len(df)}
        else:
            result = {"count": len(df)}

    report.rows_out = len(df)
    report.add_completeness(df, [status_column, value_column, date_column])
    return {"data": result, "rows": len(df), "quality_report": report.to_dict()}


def join_deals_to_work_orders(min_score: int = 75) -> dict[str, Any]:
    deals, deals_report = get_deals()
    wo, wo_report = get_work_orders()
    report = QualityReport(board="Join", rows_in=len(deals))

    matches = []
    for _, deal in deals.iterrows():
        client = str(deal.get("Client Code", "")).strip()
        deal_name = str(deal.get("Deal Name", "")).strip()
        best_wo = None
        best_score = 0
        for _, row in wo.iterrows():
            wo_client = str(row.get("Customer Name Code", "")).strip()
            if client and wo_client and client == wo_client:
                best_wo, best_score = row, 100
                break
            wo_name = str(row.get("Deal name masked", "")).strip()
            score = fuzz.ratio(deal_name.lower(), wo_name.lower())
            if score > best_score:
                best_score, best_wo = score, row
        if best_wo is not None and best_score >= min_score:
            matches.append(
                {
                    "deal_name": deal_name,
                    "client_code": client,
                    "wo_serial": best_wo.get("Serial #"),
                    "match_score": best_score,
                    "deal_status": deal.get("Deal Status"),
                    "deal_stage": deal.get("Deal Stage"),
                    "execution_status": best_wo.get("Execution Status"),
                    "invoice_status": best_wo.get("Invoice Status"),
                }
            )

    report.rows_out = len(matches)
    report.flags = [
        f"{len(deals_report.cross_check_mismatches)} deal status/stage mismatches in source",
        f"{len(wo_report.flags)} work order mapping flags in source",
    ]
    return {
        "matches": matches,
        "match_count": len(matches),
        "deals_total": len(deals),
        "work_orders_total": len(wo),
        "quality_report": report.to_dict(),
    }


def _previous_quarter_range() -> tuple[pd.Timestamp, pd.Timestamp]:
    start, _ = _current_quarter_range()
    if start.month == 1:
        prev_start = pd.Timestamp(year=start.year - 1, month=10, day=1)
        prev_end = pd.Timestamp(year=start.year, month=1, day=1) - pd.Timedelta(days=1)
    else:
        prev_start = pd.Timestamp(year=start.year, month=start.month - 3, day=1)
        prev_end = start - pd.Timedelta(days=1)
    return prev_start, prev_end


def quarter_date_range() -> dict[str, str]:
    start, end = _current_quarter_range()
    return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}


def previous_quarter_date_range() -> dict[str, str]:
    start, end = _previous_quarter_range()
    return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}


TOOL_DEFINITIONS = [
    {
        "name": "get_board_schema",
        "description": "Return column schemas and status column descriptions for both boards.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "query_deals",
        "description": "Query and aggregate Deal Tracker data.",
        "parameters": {
            "type": "object",
            "properties": {
                "sector": {"type": "string"},
                "stage": {"type": "string"},
                "status": {"type": "string"},
                "date_range": {"type": "object"},
                "group_by": {"type": "string"},
                "metric": {"type": "string", "enum": ["count", "sum"]},
                "value_column": {"type": "string"},
            },
        },
    },
    {
        "name": "query_work_orders",
        "description": "Query and aggregate Work Order Tracker data.",
        "parameters": {
            "type": "object",
            "properties": {
                "sector": {"type": "string"},
                "status": {"type": "string"},
                "status_column": {"type": "string"},
                "date_range": {"type": "object"},
                "group_by": {"type": "string"},
                "metric": {"type": "string", "enum": ["count", "sum"]},
            },
        },
    },
    {
        "name": "join_deals_to_work_orders",
        "description": "Fuzzy join deals to work orders via Client Code / Customer Name Code.",
        "parameters": {"type": "object", "properties": {}},
    },
]


def dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "get_board_schema":
        return get_board_schema()
    if name == "query_deals":
        return query_deals(**{k: v for k, v in arguments.items() if v is not None})
    if name == "query_work_orders":
        return query_work_orders(**{k: v for k, v in arguments.items() if v is not None})
    if name == "join_deals_to_work_orders":
        return join_deals_to_work_orders()
    raise ValueError(f"Unknown tool: {name}")
