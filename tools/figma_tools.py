"""
tools/figma_tools.py — Agno-compatible tool wrappers for Figma API.

These can be passed to agents as tools if you want agents to
autonomously fetch Figma data (useful for more autonomous workflows).
"""

from __future__ import annotations

import json
from agno.tools import tool
from figma_client import FigmaClient


@tool
def fetch_figma_design(figma_url: str) -> str:
    """
    Fetches and returns the full Figma file design data as JSON string.

    Args:
        figma_url: The full Figma file URL 
                   (e.g., https://www.figma.com/file/ABC123/MyDesign)

    Returns:
        JSON string of the Figma document tree
    """
    client = FigmaClient()
    file_key, _ = FigmaClient.parse_figma_url(figma_url)
    data = client.get_file(file_key)
    # Return document + metadata, trim raw to avoid token overflow
    return json.dumps({
        "name": data.get("name", "Untitled"),
        "lastModified": data.get("lastModified"),
        "document": data.get("document", {}),
        "styles": data.get("styles", {}),
        "components": data.get("components", {}),
    }, indent=2)


@tool
def fetch_figma_nodes(figma_url: str, node_ids: list[str]) -> str:
    """
    Fetches specific nodes from a Figma file by their IDs.

    Args:
        figma_url: The full Figma file URL
        node_ids:  List of node IDs to fetch (e.g., ["1:23", "4:56"])

    Returns:
        JSON string of the requested nodes
    """
    client = FigmaClient()
    file_key, _ = FigmaClient.parse_figma_url(figma_url)
    return json.dumps(client.get_file_nodes(file_key, node_ids), indent=2)


@tool
def fetch_figma_design_tokens(figma_url: str) -> str:
    """
    Fetches design variables/tokens from a Figma file.

    Args:
        figma_url: The full Figma file URL

    Returns:
        JSON string of design variables (colors, typography, spacing tokens)
    """
    client = FigmaClient()
    file_key, _ = FigmaClient.parse_figma_url(figma_url)
    try:
        variables = client.get_file_variables(file_key)
        styles = client.get_styles(file_key)
        return json.dumps({
            "variables": variables,
            "styles": styles,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "note": "Variables API requires paid Figma plan"})
