"""Work Order Tracker cleaning pipeline."""

from __future__ import annotations

import pandas as pd
from dateutil import parser as date_parser

from src.cleaning.canonical import (
    FINANCIAL_COLUMNS,
    canonicalize_sector,
    canonicalize_status,
)
from src.cleaning.quality_report import QualityReport

STATUS_COLUMNS = [
    "Execution Status",
    "WO Status (billed)",
    "Invoice Status",
    "Billing Status",
    "Collection status",
]

DATE_COLUMNS = [
    "Data Delivery Date",
    "Date of PO/LOI",
    "Probable Start Date",
    "Probable End Date",
    "Last invoice date",
    "Collection Date",
]


def _is_null(val) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return True
    return str(val).strip().lower() in {"", "nan", "none"}


def parse_date(val) -> pd.Timestamp | None:
    if _is_null(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val
    try:
        return pd.Timestamp(date_parser.parse(str(val), fuzzy=True))
    except (ValueError, TypeError, OverflowError):
        return None


def null_cause_for_financial(row: pd.Series, col: str) -> str:
    exec_status = str(row.get("Execution Status", "")).strip()
    invoice = str(row.get("Invoice Status", "")).strip()
    if _is_null(row.get(col)):
        if exec_status in {"Not Started", ""} or _is_null(exec_status):
            return "not_applicable_yet"
        if invoice in {"Not billed yet", ""} or _is_null(invoice):
            return "not_applicable_yet"
        return "true_gap"
    return "has_value"


def clean_work_orders(df: pd.DataFrame) -> tuple[pd.DataFrame, QualityReport]:
    report = QualityReport(board="Work Orders", rows_in=len(df))
    cleaned = df.copy()

    for col in DATE_COLUMNS:
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].apply(parse_date)

    for col in FINANCIAL_COLUMNS:
        if col in cleaned.columns:
            cleaned[col] = (
                cleaned[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("₹", "", regex=False)
                .str.strip()
            )
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

    if "Sector" in cleaned.columns:
        sectors, flags = [], []
        for raw in cleaned["Sector"]:
            result = canonicalize_sector(raw, "Sector")
            sectors.append(result.value)
            flags.extend(result.flags)
        cleaned["Sector"] = sectors
        report.flags.extend(f"{f.column}: '{f.raw_value}' → {f.reason}" for f in flags)

    for col in STATUS_COLUMNS:
        if col not in cleaned.columns:
            continue
        values, flags = [], []
        for raw in cleaned[col]:
            result = canonicalize_status(raw, col)
            values.append(result.value)
            flags.extend(result.flags)
        cleaned[col] = values
        report.flags.extend(f"{f.column}: '{f.raw_value}' → {f.reason}" for f in flags)

    for col in FINANCIAL_COLUMNS:
        if col in cleaned.columns:
            causes = cleaned.apply(lambda r: null_cause_for_financial(r, col), axis=1)
            report.add_null_causes(cleaned, col, causes)

    report.rows_out = len(cleaned)
    report.add_completeness(cleaned, STATUS_COLUMNS + FINANCIAL_COLUMNS[:3])
    return cleaned.reset_index(drop=True), report
