"""Read-only monday.com GraphQL API v2 client."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from src.config import MONDAY_API_TOKEN, MONDAY_API_VERSION

logger = logging.getLogger(__name__)

MONDAY_API_URL = "https://api.monday.com/v2"

# Mutations are blocked — enforced by unit test in tests/test_monday_client.py
FORBIDDEN_KEYWORDS = frozenset(
    {
        "mutation",
        "create_item",
        "update_item",
        "delete_item",
        "change_column_value",
        "create_board",
        "delete_board",
        "archive_item",
    }
)

MAX_RETRIES = 4
BACKOFF_BASE = 1.5


class MondayClientError(Exception):
    pass


class MondayClient:
    def __init__(self, api_token: str | None = None, api_version: str | None = None):
        self.api_token = api_token or MONDAY_API_TOKEN
        self.api_version = api_version or MONDAY_API_VERSION
        if not self.api_token:
            raise MondayClientError("MONDAY_API_TOKEN is not configured")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
            "API-Version": self.api_version,
        }

    def query(self, graphql: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        lowered = graphql.lower()
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in lowered:
                raise MondayClientError(f"Mutation keyword '{keyword}' is not allowed (read-only client)")

        payload: dict[str, Any] = {"query": graphql}
        if variables:
            payload["variables"] = variables

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    MONDAY_API_URL,
                    json=payload,
                    headers=self._headers(),
                    timeout=60,
                )
                if response.status_code in (429, 500, 502, 503, 504):
                    wait = BACKOFF_BASE ** attempt
                    logger.warning("monday.com %s — retry in %.1fs", response.status_code, wait)
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                data = response.json()
                if "errors" in data:
                    raise MondayClientError(str(data["errors"]))
                return data["data"]
            except requests.RequestException as exc:
                last_error = exc
                wait = BACKOFF_BASE ** attempt
                logger.warning("Request failed (%s) — retry in %.1fs", exc, wait)
                time.sleep(wait)

        raise MondayClientError(f"monday.com unreachable after {MAX_RETRIES} retries: {last_error}")

    def get_board_columns(self, board_id: str) -> list[dict[str, Any]]:
        query = """
        query ($boardId: [ID!]) {
          boards(ids: $boardId) {
            columns { id title type settings_str }
          }
        }
        """
        data = self.query(query, {"boardId": [int(board_id)]})
        boards = data.get("boards") or []
        if not boards:
            return []
        return boards[0].get("columns") or []

    def get_board_items(self, board_id: str, limit: int = 500) -> list[dict[str, Any]]:
        query = """
        query ($boardId: [ID!], $limit: Int!) {
          boards(ids: $boardId) {
            items_page(limit: $limit) {
              items {
                id
                name
                column_values { id text value type }
              }
            }
          }
        }
        """
        data = self.query(query, {"boardId": [int(board_id)], "limit": limit})
        boards = data.get("boards") or []
        if not boards:
            return []
        page = boards[0].get("items_page") or {}
        return page.get("items") or []
