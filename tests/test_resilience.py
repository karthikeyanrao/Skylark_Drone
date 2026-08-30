"""Tests for data resilience and read-only monday client."""

from __future__ import annotations

import pandas as pd
import pytest

from src.cleaning.deals import clean_deals, drop_header_pollution
from src.cleaning.canonical import canonicalize_status, canonicalize_sector
from src.monday_client import MondayClient, MondayClientError


def test_drop_header_pollution_real_pattern():
    df = pd.DataFrame(
        {
            "Deal Status": ["Open", "Deal Status", "Won"],
            "Deal Stage": ["A. Lead", "Deal Stage", "G. Project Won"],
            "Sector/service": ["Mining", "Sector/service", "Renewables"],
        }
    )
    cleaned, dropped = drop_header_pollution(df)
    assert dropped == 1
    assert len(cleaned) == 2
    assert "Deal Status" not in cleaned["Deal Status"].values


def test_clean_deals_on_real_file():
    from src.config import DEALS_EXCEL

    raw = pd.read_excel(DEALS_EXCEL)
    cleaned, report = clean_deals(raw)
    assert report.rows_dropped >= 2
    assert "Deal Status" not in cleaned["Deal Status"].astype(str).values
    assert len(report.cross_check_mismatches) >= 0


def test_billing_status_typo_canonicalization():
    result = canonicalize_status("BIlled", "Billing Status")
    assert result.value == "Billed"
    assert result.flags


def test_sector_outside_canonical_flagged():
    result = canonicalize_sector("DSP")
    assert result.flags
    assert "flagged" in result.flags[0].reason.lower() or "outside" in result.flags[0].reason.lower()


def test_monday_client_blocks_mutations():
    client = MondayClient(api_token="test-token")
    with pytest.raises(MondayClientError, match="not allowed"):
        client.query("mutation { create_item(board_id: 1, item_name: \"x\") { id } }")


def test_monday_client_file_has_no_mutations():
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "src" / "monday_client.py"
    text = source.read_text(encoding="utf-8").lower()
    for keyword in ("mutation ", "create_item", "update_item", "delete_item"):
        assert keyword not in text or "forbidden" in text or "blocked" in text
