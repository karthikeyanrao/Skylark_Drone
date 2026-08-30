"""100% free analytical agent — no API key, deterministic tool routing."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from src.data.loader import get_deals, get_work_orders
from src.tools.query_tools import (
    join_deals_to_work_orders,
    previous_quarter_date_range,
    quarter_date_range,
    query_deals,
    query_work_orders,
)


class SessionMemory:
    def __init__(self) -> None:
        self.revenue_definition: str | None = None
        self.time_framing: str | None = None
        self.energy_scope: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "revenue_definition": self.revenue_definition,
            "time_framing": self.time_framing,
            "energy_scope": self.energy_scope,
        }


def _safe_total(data: dict[str, Any]) -> float:
    total = data.get("total", 0)
    if total is None or (isinstance(total, float) and pd.isna(total)):
        return 0.0
    return float(total)


def _fmt_inr(val: float) -> str:
    if val >= 1e7:
        return f"₹{val/1e7:.2f} Cr"
    if val >= 1e5:
        return f"₹{val/1e5:.2f} L"
    return f"₹{val:,.0f}"


def _capture_session_clarifications(user_message: str, memory: SessionMemory) -> None:
    lower = user_message.lower()
    if re.search(r"\b(deal value|masked deal)\b", lower):
        memory.revenue_definition = "deal_value"
    elif re.search(r"\bbilled\b", lower):
        memory.revenue_definition = "billed"
    elif re.search(r"\b(collected|paid)\b", lower):
        memory.revenue_definition = "collected"
    if "renewables" in lower and "powerline" in lower:
        memory.energy_scope = "Renewables+Powerline"
    elif "renewables" in lower:
        memory.energy_scope = "Renewables"


def _needs_revenue_clarification(text: str, memory: SessionMemory) -> str | None:
    if memory.revenue_definition:
        return None
    if re.search(r"\b(billed|collected|paid|deal value|masked deal)\b", text, re.I):
        return None
    if re.search(r"\b(revenue|money|worth|billing)\b", text, re.I):
        return (
            "Quick clarification: when you say **revenue**, do you mean "
            "**deal value won** (Masked Deal value), **billed value**, or **collected amount**?"
        )
    return None


def _extract_sector(text: str) -> str | None:
    for s in ["mining", "renewables", "railways", "powerline", "construction", "others"]:
        if s in text:
            return s.capitalize()
    return None


def _parse_quarter_periods(text: str) -> list[tuple[str, dict[str, str] | None]]:
    periods: list[tuple[str, dict[str, str] | None]] = []
    if re.search(r"\b(this|current)\s+quarter\b", text) or re.search(
        r"\bthis\s+and\s+last\s+quarter\b", text
    ):
        periods.append(("this calendar quarter", quarter_date_range()))
    if re.search(r"\b(last|previous)\s+quarter\b", text) or re.search(
        r"\bthis\s+and\s+last\s+quarter\b", text
    ):
        periods.append(("last calendar quarter", previous_quarter_date_range()))
    if "quarter" in text and not periods:
        periods.append(("this calendar quarter", quarter_date_range()))
    return periods


def _revenue_date_column(rev: str) -> str:
    return {
        "deal_value": "Tentative Close Date",
        "billed": "Last invoice date",
        "collected": "Collection Date",
    }.get(rev, "Tentative Close Date")


def _needs_energy_clarification(text: str, memory: SessionMemory) -> str | None:
    if memory.energy_scope or not re.search(r"\benergy\b", text, re.I):
        return None
    return "For **energy sector**, should I include **Renewables only**, or **Renewables + Powerline**?"


def _parse_and_run(user_message: str, memory: SessionMemory) -> tuple[str, dict[str, Any]]:
    text = user_message.lower()
    quality_lines: list[str] = []
    context_line = ""

    # Pipeline by sector
    if re.search(r"\bpipeline\b", text):
        sector = None
        for s in ["mining", "renewables", "railways", "powerline", "construction"]:
            if s in text:
                sector = s.capitalize()
                break
        if "energy" in text and memory.energy_scope:
            sectors = memory.energy_scope.split("+")
            parts = []
            for s in sectors:
                r = query_deals(sector=s.strip(), status="Open", group_by="Deal Stage")
                quality_lines.append(r["quality_report"]["summary"])
                parts.append(f"**{s.strip()}**: {r['data']}")
            ctx = f"Open pipeline across {memory.energy_scope}."
            return ctx + "\n\n" + "\n".join(parts) + "\n\n_" + quality_lines[-1] + "_", {}

        r = query_deals(sector=sector, status="Open", group_by="Sector/service")
        quality_lines.append(r["quality_report"]["summary"])
        ctx = f"Open pipeline snapshot{' for ' + sector if sector else ''} — {r['rows']} deals."
        return (
            f"{ctx}\n\n```\n{r['data']}\n```\n\n_{quality_lines[-1]}_",
            r,
        )

    # Won / revenue
    if re.search(r"\b(won|win rate|closed won)\b", text):
        r = query_deals(status="Won", group_by="Sector/service", metric="sum")
        quality_lines.append(r["quality_report"]["summary"])
        total = r["data"].get("total", sum(v for k, v in r["data"].items() if isinstance(v, (int, float))))
        ctx = f"Won deals total {_fmt_inr(total)} across sectors."
        return f"{ctx}\n\nBy sector:\n```\n{r['data']}\n```\n\n_{quality_lines[-1]}_", r

    if re.search(r"\b(revenue|billed|collected)\b", text):
        rev = memory.revenue_definition or "deal_value"
        if "billed" in text:
            rev = "billed"
        elif "collected" in text or "paid" in text:
            rev = "collected"
        col_map = {
            "deal_value": ("Masked Deal value", "deals"),
            "billed": ("Billed Value in Rupees (Incl of GST.) (Masked)", "work_orders"),
            "collected": ("Collected Amount in Rupees (Incl of GST.) (Masked)", "work_orders"),
        }
        col, board = col_map.get(rev, col_map["deal_value"])
        date_col = _revenue_date_column(rev)
        sector = _extract_sector(text)
        periods = _parse_quarter_periods(text) if "quarter" in text else [("all time", None)]

        lines: list[str] = []
        last_r: dict[str, Any] = {}
        for label, q_range in periods:
            if board == "deals":
                r = query_deals(
                    sector=sector,
                    metric="sum",
                    value_column=col,
                    date_column=date_col,
                    date_range=q_range,
                )
            else:
                r = query_work_orders(
                    sector=sector,
                    metric="sum",
                    value_column=col,
                    date_column=date_col,
                    date_range=q_range,
                )
            quality_lines.append(r["quality_report"]["summary"])
            last_r = r
            total = _safe_total(r["data"])
            sector_note = f" · {sector}" if sector else ""
            lines.append(
                f"**{rev.replace('_', ' ').title()}** ({label}{sector_note}): "
                f"{_fmt_inr(total)} from {r['rows']} records (dated by `{date_col}`)."
            )

        if len(periods) > 1 or (periods[0][1] and (last_r.get("rows", 0) == 0)):
            if board == "work_orders":
                all_r = query_work_orders(
                    sector=sector, metric="sum", value_column=col, date_column=date_col
                )
                all_total = _safe_total(all_r["data"])
                lines.append(
                    f"_All-time{(' · ' + sector) if sector else ''}: {_fmt_inr(all_total)} "
                    f"from {all_r['rows']} work orders._"
                )

        return "\n\n".join(lines) + f"\n\n_{quality_lines[-1]}_", last_r

    # Work order / ops / delivery
    if re.search(r"\b(work order|delivery|execution|ops|operational)\b", text):
        r = query_work_orders(group_by="Execution Status")
        quality_lines.append(r["quality_report"]["summary"])
        ctx = f"Execution status distribution across {r['rows']} work orders."
        return f"{ctx}\n\n```\n{r['data']}\n```\n\n_{quality_lines[-1]}_", r

    if re.search(r"\b(billing|invoice|stuck)\b", text):
        col = "Invoice Status" if "invoice" in text else "Billing Status"
        r = query_work_orders(group_by=col)
        quality_lines.append(r["quality_report"]["summary"])
        ctx = f"{col} distribution — useful for billing backlog questions."
        return f"{ctx}\n\n```\n{r['data']}\n```\n\n_{quality_lines[-1]}_", r

    # Join / funnel
    if re.search(r"\b(join|funnel|cycle|match)\b", text):
        r = join_deals_to_work_orders()
        quality_lines.append(r["quality_report"]["summary"])
        ctx = f"Matched {r['match_count']} of {r['deals_total']} deals to work orders via client code / fuzzy name."
        sample = r["matches"][:5]
        return f"{ctx}\n\nSample matches:\n```\n{sample}\n```\n\n_{quality_lines[-1]}_", r

    # Default overview
    deals, dr = get_deals()
    wo, wr = get_work_orders()
    open_count = len(deals[deals["Deal Status"].isin(["Open", "On Hold"])])
    won_count = len(deals[deals["Deal Status"] == "Won"])
    ctx = f"Overview: {len(deals)} deals ({open_count} open, {won_count} won), {len(wo)} work orders."
    q = f"{dr.summary_line()} | {wr.summary_line()}"
    return (
        f"{ctx}\n\nTry asking about **pipeline by sector**, **won revenue**, **work order execution status**, "
        f"or type **/brief** for a leadership summary.\n\n_{q}_",
        {},
    )


def run_analytical_agent(user_message: str, memory: SessionMemory) -> str:
    if user_message.strip().lower() in {"/brief", "brief", "leadership brief"}:
        from src.brief.leadership_brief import generate_leadership_brief

        return generate_leadership_brief()

    _capture_session_clarifications(user_message, memory)

    clarify = _needs_revenue_clarification(user_message, memory) or _needs_energy_clarification(
        user_message, memory
    )
    if clarify:
        return clarify

    response, _ = _parse_and_run(user_message, memory)
    return response
