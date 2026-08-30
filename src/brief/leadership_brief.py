"""Leadership brief — deterministic, no API key required."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.data.loader import get_deals, get_work_orders
from src.tools.query_tools import quarter_date_range, query_deals, query_work_orders


def _fmt_inr(val: float) -> str:
    if val >= 1e7:
        return f"₹{val/1e7:.2f} Cr"
    if val >= 1e5:
        return f"₹{val/1e5:.2f} L"
    return f"₹{val:,.0f}"


def generate_leadership_brief() -> str:
    deals, deals_report = get_deals()
    wo, wo_report = get_work_orders()
    q_range = quarter_date_range()
    now = datetime.now().strftime("%d %b %Y")

    open_deals = deals[deals["Deal Status"].isin(["Open", "On Hold"])]
    won_deals = deals[deals["Deal Status"] == "Won"]
    pipeline_value = open_deals["Masked Deal value"].sum(min_count=1) or 0
    won_value = won_deals["Masked Deal value"].sum(min_count=1) or 0

    sector_pipeline = (
        open_deals.groupby("Sector/service", dropna=False)["Masked Deal value"]
        .sum(min_count=1)
        .sort_values(ascending=False)
        .fillna(0)
    )

    stage_counts = open_deals["Deal Stage"].fillna("Unknown").value_counts().head(8)

    exec_dist = wo["Execution Status"].fillna("Unknown").value_counts()
    invoice_dist = wo["Invoice Status"].fillna("Unknown").value_counts()
    billing_stuck = wo[wo["Billing Status"].astype(str).str.lower() == "stuck"]
    invoice_stuck = wo[wo["Invoice Status"].astype(str).str.lower() == "stuck"]

    mismatches = deals_report.cross_check_mismatches[:5]

    lines = [
        f"# Skylark Leadership Brief",
        f"*Generated {now} · Calendar QTR {q_range['start']} → {q_range['end']}*",
        "",
        "## Pipeline Snapshot",
        f"- **{len(open_deals)}** open/on-hold deals worth **{_fmt_inr(pipeline_value)}**",
        f"- **{len(won_deals)}** won deals totalling **{_fmt_inr(won_value)}**",
        "",
        "**Open pipeline by sector:**",
    ]
    for sector, val in sector_pipeline.items():
        lines.append(f"- {sector}: {_fmt_inr(val)}")

    lines += [
        "",
        "**Top open stages:**",
    ]
    for stage, cnt in stage_counts.items():
        lines.append(f"- {stage}: {cnt}")

    lines += [
        "",
        "## Revenue / Won Summary",
        f"- Won deal value (all time): **{_fmt_inr(won_value)}**",
        f"- Note: billed vs collected are separate WO fields — see ops section.",
        "",
        "## Ops Snapshot",
        f"- **{len(wo)}** work orders tracked",
        "",
        "**Execution Status:**",
    ]
    for status, cnt in exec_dist.items():
        lines.append(f"- {status}: {cnt}")

    lines += ["", "**Invoice Status:**"]
    for status, cnt in invoice_dist.items():
        lines.append(f"- {status}: {cnt}")

    lines += [
        "",
        "## Risks & Flags",
        f"- **{len(billing_stuck)}** work orders with Billing Status = Stuck",
        f"- **{len(invoice_stuck)}** work orders with Invoice Status = Stuck",
        f"- **{len(deals_report.cross_check_mismatches)}** Deal Status / Stage mismatches",
    ]
    if mismatches:
        lines.append("")
        lines.append("Sample mismatches:")
        for m in mismatches:
            lines.append(f"- {m['deal']}: {m['issue']}")

    non_canonical = deals[
        ~deals["Sector/service"].isin(
            ["Mining", "Renewables", "Railways", "Powerline", "Construction", "Others"]
        )
        & deals["Sector/service"].notna()
    ]
    if len(non_canonical):
        lines.append(f"- **{len(non_canonical)}** deals with non-canonical sector labels (DSP, Tender, etc.)")

    lines += [
        "",
        "## Data Quality",
        f"- Deals: {deals_report.summary_line()}",
        f"- Work Orders: {wo_report.summary_line()}",
        "",
        "---",
        "*Brief mode is 100% deterministic — computed in Python, no LLM cost.*",
    ]
    return "\n".join(lines)
