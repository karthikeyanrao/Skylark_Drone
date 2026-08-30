"""Per-query data quality reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class QualityReport:
    board: str
    rows_in: int = 0
    rows_out: int = 0
    rows_dropped: int = 0
    field_completeness: dict[str, float] = field(default_factory=dict)
    null_causes: dict[str, dict[str, int]] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    cross_check_mismatches: list[dict[str, Any]] = field(default_factory=list)

    def add_completeness(self, df: pd.DataFrame, columns: list[str]) -> None:
        for col in columns:
            if col not in df.columns:
                continue
            non_null = df[col].notna() & (df[col].astype(str).str.strip() != "")
            self.field_completeness[col] = round(non_null.mean() * 100, 1) if len(df) else 0.0

    def add_null_causes(self, df: pd.DataFrame, column: str, cause_series: pd.Series) -> None:
        if column not in df.columns:
            return
        null_mask = df[column].isna() | (df[column].astype(str).str.strip().isin(["", "nan", "None"]))
        causes: dict[str, int] = {}
        for cause, count in cause_series[null_mask].value_counts().items():
            causes[str(cause)] = int(count)
        if causes:
            self.null_causes[column] = causes

    def summary_line(self) -> str:
        parts: list[str] = []
        if self.rows_dropped:
            parts.append(f"dropped {self.rows_dropped} malformed/header rows")
        low = [f"{k} ({v}% complete)" for k, v in self.field_completeness.items() if v < 50]
        if low:
            parts.append(f"low completeness: {', '.join(low)}")
        if self.cross_check_mismatches:
            parts.append(f"{len(self.cross_check_mismatches)} Deal Status/Stage mismatches flagged")
        if self.flags:
            parts.append(f"{len(self.flags)} mapping flags")
        if not parts:
            return "Data quality: no significant issues detected for this query."
        return "Data quality caveat: " + "; ".join(parts) + "."

    def to_dict(self) -> dict[str, Any]:
        return {
            "board": self.board,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "rows_dropped": self.rows_dropped,
            "field_completeness": self.field_completeness,
            "null_causes": self.null_causes,
            "flags": self.flags,
            "cross_check_mismatches": self.cross_check_mismatches,
            "summary": self.summary_line(),
        }
