"""
test_parser.py — Unit tests for figma_parser.py

Run with: python -m pytest test_parser.py -v
"""

import json
import pytest
from figma_parser import FigmaParser, ParsedDesign, DesignNode, Color


# ─── Minimal Figma JSON Fixture ───────────────────────────────────────────────

MOCK_FIGMA_JSON = {
    "name": "Test Design",
    "lastModified": "2024-01-01T00:00:00Z",
    "document": {
        "id": "0:0",
        "name": "Document",
        "type": "DOCUMENT",
        "children": [
            {
                "id": "0:1",
                "name": "Page 1",
                "type": "CANVAS",
                "children": [
                    {
                        "id": "1:1",
                        "name": "HeroSection",
                        "type": "FRAME",
                        "visible": True,
                        "absoluteBoundingBox": {
                            "x": 0, "y": 0, "width": 1440, "height": 800
                        },
                        "fills": [
                            {
                                "type": "SOLID",
                                "visible": True,
                                "color": {"r": 0.1, "g": 0.1, "b": 0.1, "a": 1.0},
                                "opacity": 1.0,
                            }
                        ],
                        "strokes": [],
                        "cornerRadius": 0,
                        "opacity": 1.0,
                        "layoutMode": "VERTICAL",
                        "paddingTop": 80,
                        "paddingRight": 160,
                        "paddingBottom": 80,
                        "paddingLeft": 160,
                        "itemSpacing": 24,
                        "counterAxisAlignItems": "CENTER",
                        "primaryAxisAlignItems": "CENTER",
                        "effects": [
                            {
                                "type": "DROP_SHADOW",
                                "visible": True,
                                "color": {"r": 0, "g": 0, "b": 0, "a": 0.15},
                                "offset": {"x": 0, "y": 4},
                                "radius": 16,
                                "spread": 0,
                            }
                        ],
                        "constraints": {
                            "horizontal": "SCALE",
                            "vertical": "TOP",
                        },
                        "children": [
                            {
                                "id": "1:2",
                                "name": "Title",
                                "type": "TEXT",
                                "visible": True,
                                "characters": "Welcome to Our Product",
                                "absoluteBoundingBox": {
                                    "x": 160, "y": 300, "width": 1120, "height": 72
                                },
                                "fills": [
                                    {
                                        "type": "SOLID",
                                        "visible": True,
                                        "color": {"r": 1, "g": 1, "b": 1},
                                        "opacity": 1.0,
                                    }
                                ],
                                "style": {
                                    "fontFamily": "Inter",
                                    "fontSize": 64,
                                    "fontWeight": 700,
                                    "lineHeightPx": 72,
                                    "letterSpacing": -1.5,
                                    "textAlignHorizontal": "CENTER",
                                    "textDecoration": "NONE",
                                },
                                "effects": [],
                                "strokes": [],
                                "children": [],
                            },
                        ],
                    },
                ],
            }
        ],
    },
    "styles": {},
    "components": {},
}


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestFigmaParser:

    def setup_method(self):
        self.parser = FigmaParser()

    def test_parse_file_returns_parsed_design(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        assert isinstance(result, ParsedDesign)
        assert result.file_name == "Test Design"

    def test_root_nodes_extracted(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        assert len(result.root_nodes) == 1
        hero = result.root_nodes[0]
        assert hero.name == "HeroSection"
        assert hero.node_type == "FRAME"

    def test_bounds_parsed_correctly(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        hero = result.root_nodes[0]
        assert hero.bounds is not None
        assert hero.bounds.width == 1440
        assert hero.bounds.height == 800

    def test_fills_as_color_objects(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        hero = result.root_nodes[0]
        assert len(hero.fills) == 1
        fill = hero.fills[0]
        assert isinstance(fill, Color)
        assert fill.r == pytest.approx(0.1, abs=0.01)

    def test_color_to_hex(self):
        c = Color(r=1.0, g=0.0, b=0.0)
        assert c.to_hex() == "#FF0000"

    def test_color_to_rgba(self):
        c = Color(r=0.0, g=0.0, b=0.0, a=0.5)
        assert "rgba(0, 0, 0, 0.50)" == c.to_rgba()

    def test_text_node_parsed(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        hero = result.root_nodes[0]
        assert len(hero.children) == 1
        title = hero.children[0]
        assert title.text_content == "Welcome to Our Product"
        assert title.text_style is not None
        assert title.text_style.font_size == 64
        assert title.text_style.font_weight == 700
        assert title.text_style.font_family == "Inter"

    def test_auto_layout_parsed(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        hero = result.root_nodes[0]
        assert hero.auto_layout is not None
        assert hero.auto_layout.direction == "VERTICAL"
        assert hero.auto_layout.padding_top == 80
        assert hero.auto_layout.item_spacing == 24

    def test_effects_parsed(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        hero = result.root_nodes[0]
        assert len(hero.effects) == 1
        assert "DROP_SHADOW" in hero.effects[0]["type"]
        assert "px" in hero.effects[0]["css"]

    def test_constraints_parsed(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        hero = result.root_nodes[0]
        assert hero.constraints["horizontal"] == "SCALE"
        assert hero.constraints["vertical"] == "TOP"

    def test_design_tokens_extracted(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        tokens = result.tokens
        assert isinstance(tokens.font_families, list)
        assert "Inter" in tokens.font_families
        assert 64.0 in tokens.font_sizes
        assert 700 in tokens.font_weights
        # Padding values collected
        assert 80.0 in tokens.spacing_values

    def test_css_variables_generation(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        css = result.tokens.to_css_variables()
        assert ":root {" in css
        assert "--font-size-" in css
        assert "--spacing-" in css

    def test_node_to_dict(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON)
        hero = result.root_nodes[0]
        d = hero.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "HeroSection"
        assert "bounds" in d
        assert "children" in d

    def test_target_node_id_filtering(self):
        result = self.parser.parse_file(MOCK_FIGMA_JSON, target_node_id="1:1")
        assert len(result.root_nodes) == 1
        assert result.root_nodes[0].id == "1:1"

    def test_parse_file_empty_document(self):
        empty = {
            "name": "Empty",
            "lastModified": "",
            "document": {"id": "0:0", "name": "Doc", "type": "DOCUMENT", "children": []},
            "styles": {},
            "components": {},
        }
        result = self.parser.parse_file(empty)
        assert result.root_nodes == []


class TestFigmaClientURLParsing:

    def test_parse_standard_file_url(self):
        from figma_client import FigmaClient
        url = "https://www.figma.com/file/ABC123xyz/My-Design"
        key, node = FigmaClient.parse_figma_url(url)
        assert key == "ABC123xyz"
        assert node is None

    def test_parse_file_url_with_node_id(self):
        from figma_client import FigmaClient
        url = "https://www.figma.com/file/ABC123xyz/My-Design?node-id=1-23"
        key, node = FigmaClient.parse_figma_url(url)
        assert key == "ABC123xyz"
        assert node == "1:23"

    def test_parse_design_url(self):
        from figma_client import FigmaClient
        url = "https://www.figma.com/design/XYZ789/Prototype"
        key, node = FigmaClient.parse_figma_url(url)
        assert key == "XYZ789"

    def test_invalid_url_raises(self):
        from figma_client import FigmaClient
        with pytest.raises(ValueError):
            FigmaClient.parse_figma_url("https://example.com/not-figma")


class TestCodeTools:

    def test_to_pascal_case(self):
        from tools.code_tools import to_pascal_case
        assert to_pascal_case("hero section") == "HeroSection"
        assert to_pascal_case("hero-section/card") == "HeroSectionCard"
        assert to_pascal_case("Button") == "Button"

    def test_to_kebab_case(self):
        from tools.code_tools import to_kebab_case
        assert to_kebab_case("HeroSection") == "hero-section"
        assert to_kebab_case("MyCard") == "my-card"

    def test_extract_code_blocks(self):
        from tools.code_tools import extract_code_blocks
        text = "Here is the code:\n```tsx\nconst x = 1;\n```\nDone."
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert "const x = 1;" in blocks[0]

    def test_validate_tsx_basics_any_warning(self):
        from tools.code_tools import validate_tsx_basics
        code = "const f = (x: any) => x;"
        warnings = validate_tsx_basics(code)
        assert any("any" in w for w in warnings)

    def test_validate_tsx_missing_export(self):
        from tools.code_tools import validate_tsx_basics
        code = "const Button = () => <button>Click</button>;"
        warnings = validate_tsx_basics(code)
        assert any("export" in w for w in warnings)
