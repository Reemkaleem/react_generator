"""
tools/code_tools.py — Code validation and formatting utilities.

Helper functions used by the pipeline and agents for post-processing
LLM-generated React/TypeScript code.
"""

from __future__ import annotations

import re
import json


def to_pascal_case(name: str) -> str:
    """
    Converts a Figma layer name to PascalCase component name.
    e.g., "hero section / card" → "HeroSectionCard"
    """
    # Remove special chars, split on space/dash/slash/underscore
    parts = re.split(r"[\s\-_/\\]+", name)
    return "".join(p.capitalize() for p in parts if p)


def to_kebab_case(name: str) -> str:
    """
    Converts PascalCase to kebab-case for CSS classes.
    e.g., "HeroCard" → "hero-card"
    """
    s = re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()
    return re.sub(r"[\s_/\\]+", "-", s)


def extract_code_blocks(text: str) -> list[str]:
    """
    Extracts all code blocks from markdown-formatted LLM output.
    Returns a list of code strings (content inside ```...```).
    """
    pattern = r"```(?:\w+)?\n?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches]


def clean_llm_json(text: str) -> str:
    """
    Strips common LLM artifacts from JSON responses:
    - Markdown code fences
    - Leading/trailing whitespace and explanatory text
    """
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()


def validate_tsx_basics(tsx_code: str) -> list[str]:
    """
    Performs basic validation checks on TSX code.
    Returns a list of warning strings (empty = all good).
    """
    warnings = []

    if re.search(r":\s*any[\s;,)\]>]", tsx_code) or "any>" in tsx_code:
        warnings.append("Uses 'any' type — should be replaced with proper types")

    if "style={{" in tsx_code:
        occurrences = tsx_code.count("style={{")
        if occurrences > 3:
            warnings.append(f"Heavy use of inline styles ({occurrences}x) — prefer CSS Modules")

    if "className=" in tsx_code and "styles." not in tsx_code:
        warnings.append("className used without CSS Modules import")

    if "<img" in tsx_code and 'alt=' not in tsx_code:
        warnings.append("Image elements missing alt attribute")

    if "<button" in tsx_code and "type=" not in tsx_code:
        warnings.append("Button elements missing type attribute")

    if "key={index}" in tsx_code or "key={i}" in tsx_code:
        warnings.append("Array index used as key — prefer stable IDs")

    if "export default" not in tsx_code:
        warnings.append("Component missing default export")

    if "import React" not in tsx_code and "from 'react'" not in tsx_code:
        warnings.append("React import may be missing")

    return warnings


def generate_storybook_story(component_name: str, props_interface: dict) -> str:
    """
    Generates a basic Storybook story for a component.
    """
    args_str = ""
    for prop_name, prop_info in props_interface.items():
        if not prop_info.get("required", False):
            continue
        prop_type = prop_info.get("type", "string")
        if prop_type == "string":
            args_str += f"  {prop_name}: 'Sample {prop_name}',\n"
        elif prop_type == "boolean":
            args_str += f"  {prop_name}: true,\n"
        elif prop_type == "number":
            args_str += f"  {prop_name}: 0,\n"
        else:
            args_str += f"  {prop_name}: undefined,\n"

    return f"""import type {{ Meta, StoryObj }} from '@storybook/react';
import {component_name} from './{component_name}';

const meta: Meta<typeof {component_name}> = {{
  title: 'Components/{component_name}',
  component: {component_name},
  tags: ['autodocs'],
}};

export default meta;
type Story = StoryObj<typeof {component_name}>;

export const Default: Story = {{
  args: {{
{args_str}  }},
}};
"""
