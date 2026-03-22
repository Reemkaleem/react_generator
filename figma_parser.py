"""
figma_parser.py — Normalizes raw Figma JSON into clean Python dataclasses.

Produces a DesignNode tree and a flat DesignTokens dict that agents can
reason about without dealing with nested Figma internals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class Color:
    r: float
    g: float
    b: float
    a: float = 1.0

    def to_hex(self) -> str:
        """Returns CSS hex color string, e.g. #1A2B3C"""
        r = int(self.r * 255)
        g = int(self.g * 255)
        b = int(self.b * 255)
        return f"#{r:02X}{g:02X}{b:02X}"

    def to_rgba(self) -> str:
        return f"rgba({int(self.r*255)}, {int(self.g*255)}, {int(self.b*255)}, {self.a:.2f})"


@dataclass
class Bounds:
    x: float
    y: float
    width: float
    height: float


@dataclass
class TextStyle:
    font_family: str = "Inter"
    font_size: float = 14.0
    font_weight: int = 400
    line_height: float | None = None
    letter_spacing: float = 0.0
    text_align: str = "left"
    text_decoration: str = "none"


@dataclass
class AutoLayout:
    direction: str = "NONE"          # HORIZONTAL | VERTICAL | NONE
    padding_top: float = 0
    padding_right: float = 0
    padding_bottom: float = 0
    padding_left: float = 0
    item_spacing: float = 0
    align_items: str = "AUTO"        # MIN | CENTER | MAX | SPACE_BETWEEN
    justify_content: str = "AUTO"
    wrap: bool = False


@dataclass
class DesignNode:
    """
    Normalized representation of a single Figma node.
    All child nodes are stored recursively.
    """
    id: str
    name: str
    node_type: str              # FRAME, GROUP, COMPONENT, TEXT, RECTANGLE, etc.
    bounds: Bounds | None = None
    fills: list[Color] = field(default_factory=list)
    strokes: list[Color] = field(default_factory=list)
    stroke_width: float = 0.0
    border_radius: float | list[float] = 0.0
    opacity: float = 1.0
    text_content: str | None = None
    text_style: TextStyle | None = None
    auto_layout: AutoLayout | None = None
    constraints: dict[str, str] = field(default_factory=dict)
    children: list["DesignNode"] = field(default_factory=list)
    is_component: bool = False
    component_id: str | None = None
    effects: list[dict] = field(default_factory=list)   # shadows, blurs
    visible: bool = True
    # Raw figma properties preserved for agent access
    raw_clips: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class DesignTokens:
    """Flat dictionary of design-system tokens extracted from a Figma file."""
    colors: dict[str, str] = field(default_factory=dict)        # name → hex
    font_families: list[str] = field(default_factory=list)
    font_sizes: list[float] = field(default_factory=list)
    font_weights: list[int] = field(default_factory=list)
    spacing_values: list[float] = field(default_factory=list)
    border_radii: list[float] = field(default_factory=list)
    shadows: list[str] = field(default_factory=list)            # CSS box-shadow strings
    variables: dict[str, Any] = field(default_factory=dict)     # Figma variables

    def to_css_variables(self) -> str:
        """Generates a CSS :root block with all tokens as custom properties."""
        lines = [":root {"]
        for name, hex_val in self.colors.items():
            css_name = name.lower().replace(" ", "-").replace("/", "-")
            lines.append(f"  --color-{css_name}: {hex_val};")
        for i, size in enumerate(sorted(set(self.font_sizes))):
            lines.append(f"  --font-size-{i}: {size}px;")
        for i, spacing in enumerate(sorted(set(self.spacing_values))):
            lines.append(f"  --spacing-{i}: {spacing}px;")
        lines.append("}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParsedDesign:
    """Top-level result of parsing a Figma file."""
    file_key: str
    file_name: str
    root_nodes: list[DesignNode]        # Top-level frames/pages
    tokens: DesignTokens
    components: dict[str, DesignNode]   # component_id → DesignNode


# ─── Parser ───────────────────────────────────────────────────────────────────

class FigmaParser:
    """
    Converts raw Figma API JSON into a clean ParsedDesign.
    Walks the document tree recursively and extracts all design info.
    """

    # Node types we should generate React components for
    COMPONENT_TYPES = {"FRAME", "COMPONENT", "COMPONENT_SET", "INSTANCE", "GROUP"}

    def parse_file(
        self,
        figma_json: dict[str, Any],
        target_node_id: str | None = None,
    ) -> ParsedDesign:
        """Parse a full Figma file JSON (from FigmaClient.get_file)."""
        document = figma_json.get("document", {})
        styles = figma_json.get("styles", {})
        components = figma_json.get("components", {})

        # Build token map first (needed during node parsing)
        tokens = self._extract_tokens(figma_json)

        # Parse node tree
        root_nodes: list[DesignNode] = []
        if target_node_id:
            # Find specific node
            target = self._find_node(document, target_node_id)
            if target:
                root_nodes = [self._parse_node(target)]
        else:
            # Parse all canvas pages
            for page in document.get("children", []):
                for child in page.get("children", []):
                    if child.get("type") in self.COMPONENT_TYPES:
                        root_nodes.append(self._parse_node(child))

        # Parse components map
        component_map: dict[str, DesignNode] = {}
        for comp_id, comp_data in components.items():
            node_raw = self._find_node(document, comp_id)
            if node_raw:
                component_map[comp_id] = self._parse_node(node_raw)

        return ParsedDesign(
            file_key=figma_json.get("lastModified", "unknown"),
            file_name=figma_json.get("name", "Untitled"),
            root_nodes=root_nodes,
            tokens=tokens,
            components=component_map,
        )

    def parse_nodes(self, nodes_json: dict[str, Any]) -> list[DesignNode]:
        """Parse a nodes response (from FigmaClient.get_file_nodes)."""
        parsed = []
        for node_id, node_data in nodes_json.get("nodes", {}).items():
            if node_data and "document" in node_data:
                parsed.append(self._parse_node(node_data["document"]))
        return parsed

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_node(self, tree: dict, target_id: str) -> dict | None:
        """Depth-first search for a node by ID."""
        if tree.get("id") == target_id:
            return tree
        for child in tree.get("children", []):
            result = self._find_node(child, target_id)
            if result:
                return result
        return None

    def _parse_node(self, raw: dict) -> DesignNode:
        """Recursively parse a single Figma node."""
        bounds = None
        ab = raw.get("absoluteBoundingBox") or raw.get("absoluteRenderBounds")
        if ab:
            bounds = Bounds(
                x=ab.get("x", 0),
                y=ab.get("y", 0),
                width=ab.get("width", 0),
                height=ab.get("height", 0),
            )

        fills = self._parse_colors(raw.get("fills", []))
        strokes = self._parse_colors(raw.get("strokes", []))

        # Border radius
        br_raw = raw.get("cornerRadius", 0) or 0
        rect_corners = raw.get("rectangleCornerRadii")
        border_radius: float | list[float] = (
            rect_corners if rect_corners else float(br_raw)
        )

        # Text
        text_content = raw.get("characters") if raw.get("type") == "TEXT" else None
        text_style = self._parse_text_style(raw.get("style")) if text_content else None

        # Auto-layout
        auto_layout = self._parse_auto_layout(raw)

        # Constraints
        constraints = {}
        if "constraints" in raw:
            constraints = {
                "horizontal": raw["constraints"].get("horizontal", "LEFT"),
                "vertical": raw["constraints"].get("vertical", "TOP"),
            }

        # Effects (shadows etc.)
        effects = []
        for eff in raw.get("effects", []):
            if eff.get("visible", True):
                effects.append(self._parse_effect(eff))

        # Recurse children
        children = [
            self._parse_node(child)
            for child in raw.get("children", [])
            if child.get("visible", True) is not False
        ]

        return DesignNode(
            id=raw.get("id", ""),
            name=raw.get("name", "unnamed"),
            node_type=raw.get("type", "UNKNOWN"),
            bounds=bounds,
            fills=fills,
            strokes=strokes,
            stroke_width=raw.get("strokeWeight", 0) or 0,
            border_radius=border_radius,
            opacity=raw.get("opacity", 1.0),
            text_content=text_content,
            text_style=text_style,
            auto_layout=auto_layout,
            constraints=constraints,
            children=children,
            is_component=raw.get("type") in {"COMPONENT", "INSTANCE"},
            component_id=raw.get("componentId"),
            effects=effects,
            visible=raw.get("visible", True),
            raw_clips=raw.get("clipsContent", False),
        )

    def _parse_colors(self, paints: list[dict]) -> list[Color]:
        colors = []
        for paint in paints:
            if not paint.get("visible", True):
                continue
            if paint.get("type") == "SOLID":
                c = paint.get("color", {})
                colors.append(Color(
                    r=c.get("r", 0),
                    g=c.get("g", 0),
                    b=c.get("b", 0),
                    a=paint.get("opacity", 1.0),
                ))
        return colors

    def _parse_text_style(self, style: dict | None) -> TextStyle | None:
        if not style:
            return None
        lh = style.get("lineHeightPx")
        return TextStyle(
            font_family=style.get("fontFamily", "Inter"),
            font_size=style.get("fontSize", 14),
            font_weight=style.get("fontWeight", 400),
            line_height=lh if lh and lh > 0 else None,
            letter_spacing=style.get("letterSpacing", 0),
            text_align=style.get("textAlignHorizontal", "LEFT").lower(),
            text_decoration=style.get("textDecoration", "NONE").lower(),
        )

    def _parse_auto_layout(self, raw: dict) -> AutoLayout | None:
        if raw.get("layoutMode") not in {"HORIZONTAL", "VERTICAL"}:
            return None
        padding = raw.get("paddingTop", 0)
        return AutoLayout(
            direction=raw.get("layoutMode", "NONE"),
            padding_top=raw.get("paddingTop", padding),
            padding_right=raw.get("paddingRight", padding),
            padding_bottom=raw.get("paddingBottom", padding),
            padding_left=raw.get("paddingLeft", padding),
            item_spacing=raw.get("itemSpacing", 0),
            align_items=raw.get("counterAxisAlignItems", "MIN"),
            justify_content=raw.get("primaryAxisAlignItems", "MIN"),
            wrap=raw.get("layoutWrap") == "WRAP",
        )

    def _parse_effect(self, eff: dict) -> dict:
        eff_type = eff.get("type", "")
        color = eff.get("color", {})
        c = Color(
            r=color.get("r", 0),
            g=color.get("g", 0),
            b=color.get("b", 0),
            a=color.get("a", 0.25),
        )
        offset = eff.get("offset", {"x": 0, "y": 4})
        radius = eff.get("radius", 4)
        spread = eff.get("spread", 0)
        inset = "inset " if eff_type == "INNER_SHADOW" else ""
        css = (
            f"{inset}{offset.get('x', 0)}px {offset.get('y', 4)}px "
            f"{radius}px {spread}px {c.to_rgba()}"
        )
        return {"type": eff_type, "css": css}

    def _extract_tokens(self, figma_json: dict) -> DesignTokens:
        """Walk entire document to collect all design tokens."""
        tokens = DesignTokens()
        styles_map = figma_json.get("styles", {})
        document = figma_json.get("document", {})

        # Collect from styles
        for style_id, style_info in styles_map.items():
            name = style_info.get("name", "")
            style_type = style_info.get("styleType", "")
            if style_type == "FILL":
                tokens.colors[name] = ""  # will be filled from node traversal
            elif style_type == "TEXT":
                pass  # text styles filled below

        # Walk tree to collect values
        self._walk_for_tokens(document, tokens)

        # Remove duplicates and sort
        tokens.font_sizes = sorted(set(tokens.font_sizes))
        tokens.font_weights = sorted(set(tokens.font_weights))
        tokens.spacing_values = sorted(set(v for v in tokens.spacing_values if v > 0))
        tokens.border_radii = sorted(set(v for v in tokens.border_radii if v > 0))

        return tokens

    def _walk_for_tokens(self, node: dict, tokens: DesignTokens):
        """DFS walk to harvest token values."""
        # Colors from fills
        for paint in node.get("fills", []):
            if paint.get("type") == "SOLID" and paint.get("visible", True):
                c = paint.get("color", {})
                color = Color(c.get("r", 0), c.get("g", 0), c.get("b", 0))
                hex_val = color.to_hex()
                name = node.get("name", f"color-{len(tokens.colors)}")
                if hex_val not in tokens.colors.values():
                    tokens.colors[name] = hex_val

        # Text
        if style := node.get("style"):
            ff = style.get("fontFamily")
            if ff and ff not in tokens.font_families:
                tokens.font_families.append(ff)
            if fs := style.get("fontSize"):
                tokens.font_sizes.append(float(fs))
            if fw := style.get("fontWeight"):
                tokens.font_weights.append(int(fw))

        # Auto-layout spacing
        for key in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "itemSpacing"):
            if val := node.get(key):
                tokens.spacing_values.append(float(val))

        # Border radius
        if cr := node.get("cornerRadius"):
            tokens.border_radii.append(float(cr))

        # Effects (shadows)
        for eff in node.get("effects", []):
            if eff.get("visible", True):
                parsed = self._parse_effect(eff)
                if parsed.get("css") not in tokens.shadows:
                    tokens.shadows.append(parsed["css"])

        for child in node.get("children", []):
            self._walk_for_tokens(child, tokens)
