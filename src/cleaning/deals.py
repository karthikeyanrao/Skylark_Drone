"""Deal Tracker cleaning pipeline."""

from __future__ import annotations

import pandas as pd
from dateutil import parser as date_parser

from src.cleaning.canonical import canonicalize_sector
from src.cleaning.quality_report import QualityReport
from src.config import LOST_STAGES, WON_STAGES


def _is_null(val) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return True
    return str(val).strip().lower() in {"", "nan", "none"}


def drop_header_pollution(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop rows where >=2 cells equal their own column header."""
    if df.empty:
        return df, 0
    header_matches = pd.DataFrame(
        {col: df[col].astype(str).str.strip() == str(col).strip() for col in df.columns}
    )
    mask = header_matches.sum(axis=1) >= 2
    dropped = int(mask.sum())
    return df[~mask].copy(), dropped


def parse_date(val) -> pd.Timestamp | None:
    if _is_null(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val
    try:
        return pd.Timestamp(date_parser.parse(str(val), fuzzy=True))
    except (ValueError, TypeError, OverflowError):
        return None


def classify_deal_status_stage(row: pd.Series) -> str | None:
    status = str(row.get("Deal Status", "")).strip()
    stage = str(row.get("Deal Stage", "")).strip()
    if _is_null(status) or _is_null(stage):
        return None
    if status == "Won" and stage not in WON_STAGES:
        return "Won status but stage not in G/H/J/K"
    if status == "Dead" and stage in WON_STAGES:
        return "Dead status but stage indicates won"
    if status in {"Open", "On Hold"} and stage in LOST_STAGES:
        return "Open/On Hold status but lost stage"
    return None


def clean_deals(df: pd.DataFrame) -> tuple[pd.DataFrame, QualityReport]:
    report = QualityReport(board="Deals", rows_in=len(df))
    cleaned, dropped = drop_header_pollution(df)
    report.rows_dropped = dropped

    for col in ("Close Date (A)", "Tentative Close Date", "Created Date"):
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].apply(parse_date)

    if "Masked Deal value" in cleaned.columns:
        cleaned["Masked Deal value"] = (
            cleaned["Masked Deal value"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("₹", "", regex=False)
            .str.strip()
        )
        cleaned["Masked Deal value"] = pd.to_numeric(cleaned["Masked Deal value"], errors="coerce")

    if "Sector/service" in cleaned.columns:
        sectors, flags = [], []
        for raw in cleaned["Sector/service"]:
            result = canonicalize_sector(raw, "Sector/service")
            sectors.append(result.value)
            flags.extend(result.flags)
        cleaned["Sector/service"] = sectors
        report.flags.extend(f"{f.column}: '{f.raw_value}' → {f.reason}" for f in flags)

    mismatches = []
    for _, row in cleaned.iterrows():
        issue = classify_deal_status_stage(row)
        if issue:
            mismatches.append(
                {
                    "deal": row.get("Deal Name"),
                    "status": row.get("Deal Status"),
                    "stage": row.get("Deal Stage"),
                    "issue": issue,
                }
            )
    report.cross_check_mismatches = mismatches

    report.rows_out = len(cleaned)
    report.add_completeness(
        cleaned,
        [
            "Deal Status",
            "Deal Stage",
            "Masked Deal value",
            "Sector/service",
            "Close Date (A)",
            "Closure Probability",
        ],
    )
    return cleaned.reset_index(drop=True), report
