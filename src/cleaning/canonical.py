"""Canonical vocabularies and fuzzy mapping for dirty labels."""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from src.config import CANONICAL_SECTORS

# Built from observed Work Order Billing Status values — not blind fuzzy matching
BILLING_STATUS_CANONICAL: dict[str, str] = {
    "billed": "Billed",
    "billled": "Billed",
    "update required": "Update Required",
    "not billable": "Not Billable",
    "partially billed": "Partially Billed",
    "stuck": "Stuck",
}

EXECUTION_STATUS_CANONICAL: dict[str, str] = {
    "completed": "Completed",
    "ongoing": "Ongoing",
    "executed until current month": "Executed until current month",
    "not started": "Not Started",
    "pause / struck": "Pause / struck",
    "partial completed": "Partial Completed",
    "details pending from client": "Details pending from Client",
}

INVOICE_STATUS_CANONICAL: dict[str, str] = {
    "fully billed": "Fully Billed",
    "partially billed": "Partially Billed",
    "not billed yet": "Not billed yet",
    "stuck": "Stuck",
}

WO_STATUS_CANONICAL: dict[str, str] = {
    "closed": "Closed",
    "open": "Open",
}

COLLECTION_STATUS_CANONICAL: dict[str, str] = {
    "collected": "Collected",
    "partially collected": "Partially Collected",
    "pending": "Pending",
}

STATUS_COLUMN_DESCRIPTIONS: dict[str, str] = {
    "Execution Status": "Delivery/execution progress — use for 'delivered' or 'in progress' questions.",
    "WO Status (billed)": "Work-order billing lifecycle (Open/Closed) — use for WO-level billed state.",
    "Invoice Status": "Invoice issuance state (Fully/Partially Billed, Stuck) — use for invoicing questions.",
    "Billing Status": "Billing ops queue state (Update Required, Stuck) — use for billing backlog questions.",
    "Collection status": "Payment collection state — use for 'paid/collected' questions (often sparse).",
}

FINANCIAL_COLUMNS = [
    "Amount in Rupees (Excl of GST) (Masked)",
    "Amount in Rupees (Incl of GST) (Masked)",
    "Billed Value in Rupees (Excl of GST.) (Masked)",
    "Billed Value in Rupees (Incl of GST.) (Masked)",
    "Collected Amount in Rupees (Incl of GST.) (Masked)",
    "Amount to be billed in Rs. (Exl. of GST) (Masked)",
    "Amount to be billed in Rs. (Incl. of GST) (Masked)",
    "Amount Receivable (Masked)",
]

QUANTITY_COLUMNS = [
    "Quantity by Ops",
    "Quantities as per PO",
    "Quantity billed (till date)",
    "Balance in quantity",
]

DEALS_COLUMNS = [
    "Deal Name",
    "Owner code",
    "Client Code",
    "Deal Status",
    "Close Date (A)",
    "Closure Probability",
    "Masked Deal value",
    "Tentative Close Date",
    "Deal Stage",
    "Product deal",
    "Sector/service",
    "Created Date",
]

WORK_ORDERS_COLUMNS = [
    "Deal name masked",
    "Customer Name Code",
    "Serial #",
    "Nature of Work",
    "Execution Status",
    "Data Delivery Date",
    "Date of PO/LOI",
    "Document Type",
    "Probable Start Date",
    "Probable End Date",
    "BD/KAM Personnel code",
    "Sector",
    "Type of Work",
    "Last invoice date",
    "latest invoice no.",
    *FINANCIAL_COLUMNS,
    *QUANTITY_COLUMNS,
    "Invoice Status",
    "WO Status (billed)",
    "Billing Status",
    "Collection status",
    "Collection Date",
    "AR Priority account",
]


@dataclass
class MappingFlag:
    column: str
    raw_value: str
    mapped_value: str | None
    reason: str


@dataclass
class CanonicalResult:
    value: str | None
    flags: list[MappingFlag] = field(default_factory=list)


def _lookup_canonical(raw: str | None, table: dict[str, str], column: str) -> CanonicalResult:
    if raw is None or (isinstance(raw, float) and str(raw) == "nan"):
        return CanonicalResult(value=None)
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none", ""}:
        return CanonicalResult(value=None)
    key = text.lower()
    if key in table:
        mapped = table[key]
        if mapped != text:
            return CanonicalResult(
                value=mapped,
                flags=[MappingFlag(column, text, mapped, "typo/case normalized via lookup table")],
            )
        return CanonicalResult(value=mapped)
    return CanonicalResult(
        value=text,
        flags=[MappingFlag(column, text, None, "unmapped value — kept as-is")],
    )


def canonicalize_sector(raw: str | None, column: str = "Sector/service") -> CanonicalResult:
    if raw is None or str(raw).strip().lower() in {"", "nan", "none"}:
        return CanonicalResult(value=None)
    text = str(raw).strip()
    if text in CANONICAL_SECTORS:
        return CanonicalResult(value=text)
    match = process.extractOne(text, list(CANONICAL_SECTORS), scorer=fuzz.ratio)
    if match and match[1] >= 85:
        return CanonicalResult(
            value=match[0],
            flags=[MappingFlag(column, text, match[0], f"fuzzy sector match ({match[1]}% confidence)")],
        )
    return CanonicalResult(
        value=text,
        flags=[MappingFlag(column, text, None, "outside canonical 6-sector set — flagged for review")],
    )


def canonicalize_status(raw: str | None, column: str) -> CanonicalResult:
    tables = {
        "Billing Status": BILLING_STATUS_CANONICAL,
        "Execution Status": EXECUTION_STATUS_CANONICAL,
        "Invoice Status": INVOICE_STATUS_CANONICAL,
        "WO Status (billed)": WO_STATUS_CANONICAL,
        "Collection status": COLLECTION_STATUS_CANONICAL,
    }
    table = tables.get(column, {})
    return _lookup_canonical(raw, table, column)
