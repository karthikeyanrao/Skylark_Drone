"""pytest configuration — force Excel fallback path for all tests."""

from __future__ import annotations

import os


def pytest_configure(config):  # noqa: ANN001
    """Set environment flags before any module is imported in the test session."""
    os.environ.setdefault("PYTEST_RUNNING", "1")
    os.environ.setdefault("DATA_SOURCE", "local")
    os.environ.setdefault("AGENT_MODE", "analytical")
