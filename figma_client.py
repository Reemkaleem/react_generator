"""
figma_client.py — Figma REST API wrapper.

Handles authentication and all HTTP calls to the Figma v1 API.
"""

from __future__ import annotations

import re
import time
import requests
from typing import Any

from config import (
    FIGMA_ACCESS_TOKEN,
    FIGMA_BASE_URL,
    FIGMA_MAX_RETRIES,
    FIGMA_RETRY_BASE_DELAY,
    FIGMA_RETRY_MAX_DELAY,
)


class FigmaAPIError(Exception):
    """Raised when the Figma API returns an error."""
    pass


class FigmaClient:
    """
    Thin wrapper around the Figma REST API v1.
    All methods return the raw JSON dict from Figma.
    """

    def __init__(self, access_token: str = FIGMA_ACCESS_TOKEN):
        if not access_token:
            raise ValueError(
                "Figma access token is required. "
                "Set FIGMA_ACCESS_TOKEN in your .env file."
            )
        self.session = requests.Session()
        self.session.headers.update({
            "X-Figma-Token": access_token,
            "Content-Type": "application/json",
        })
        self.max_retries = max(0, FIGMA_MAX_RETRIES)
        self.retry_base_delay = max(0.1, FIGMA_RETRY_BASE_DELAY)
        self.retry_max_delay = max(self.retry_base_delay, FIGMA_RETRY_MAX_DELAY)

    def _get_retry_delay(self, response: requests.Response, attempt: int) -> float:
        """Computes retry delay from Retry-After header or exponential backoff."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), self.retry_max_delay)
            except ValueError:
                pass
        return min(self.retry_base_delay * (2 ** attempt), self.retry_max_delay)

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{FIGMA_BASE_URL}{path}"
        retriable_statuses = {429, 500, 502, 503, 504}

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, params=params or {}, timeout=30)
            except requests.RequestException as e:
                if attempt < self.max_retries:
                    delay = min(self.retry_base_delay * (2 ** attempt), self.retry_max_delay)
                    time.sleep(delay)
                    continue
                raise FigmaAPIError(f"Figma API request failed: {e}") from e

            if response.status_code == 200:
                data = response.json()
                if "error" in data and data.get("status", 200) != 200:
                    raise FigmaAPIError(f"Figma API returned error: {data}")
                return data

            if response.status_code in retriable_statuses and attempt < self.max_retries:
                time.sleep(self._get_retry_delay(response, attempt))
                continue

            raise FigmaAPIError(
                f"Figma API error [{response.status_code}] after {attempt} retries: {response.text}"
            )

        raise FigmaAPIError("Figma API request failed after retries.")

    # ── File-level ────────────────────────────────────────────────────────────

    def get_file(self, file_key: str) -> dict[str, Any]:
        """
        Fetch the full document tree for a Figma file.
        Returns a dict with 'document', 'components', 'styles', etc.
        """
        return self._get(f"/files/{file_key}")

    def get_file_nodes(
        self, file_key: str, node_ids: list[str]
    ) -> dict[str, Any]:
        """Fetch a subset of nodes by their IDs."""
        ids = ",".join(node_ids)
        return self._get(f"/files/{file_key}/nodes", params={"ids": ids})

    def get_images(
        self,
        file_key: str,
        node_ids: list[str],
        scale: float = 1.0,
        fmt: str = "png",
    ) -> dict[str, str]:
        """
        Get image export URLs for specific nodes.
        Returns {node_id: image_url, ...}
        """
        data = self._get(
            f"/images/{file_key}",
            params={
                "ids": ",".join(node_ids),
                "scale": scale,
                "format": fmt,
            },
        )
        return data.get("images", {})

    def get_file_variables(self, file_key: str) -> dict[str, Any]:
        """
        Fetch design variables (tokens) for a file.
        Returns collections and variables dicts.
        """
        return self._get(f"/files/{file_key}/variables/local")

    def get_components(self, file_key: str) -> dict[str, Any]:
        """Fetch all published components in a file."""
        return self._get(f"/files/{file_key}/components")

    def get_styles(self, file_key: str) -> dict[str, Any]:
        """Fetch all styles (colors, text styles) defined in a file."""
        return self._get(f"/files/{file_key}/styles")

    # ── URL Parsing ───────────────────────────────────────────────────────────

    @staticmethod
    def parse_figma_url(url: str) -> tuple[str, str | None]:
        """
        Parses a Figma URL into (file_key, node_id).

        Supported formats:
          https://www.figma.com/file/<key>/Title?node-id=<id>
          https://www.figma.com/design/<key>/Title?node-id=<id>
          https://www.figma.com/community/file/<key>
        """
        # Match /file/<key> or /design/<key>
        match = re.search(
            r"figma\.com/(?:file|design)/([a-zA-Z0-9]+)", url
        )
        if not match:
            # Try community file pattern
            match = re.search(r"figma\.com/community/file/(\d+)", url)
        if not match:
            raise ValueError(
                f"Cannot extract file key from URL: {url}\n"
                "Expected a URL like: https://www.figma.com/file/<key>/Title"
            )

        file_key = match.group(1)

        # Extract optional node-id
        node_match = re.search(r"node-id=([^&]+)", url)
        node_id = node_match.group(1).replace("-", ":") if node_match else None

        return file_key, node_id
