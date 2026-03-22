"""
agents/team.py — Agno Pipeline Orchestrator for Figma → React conversion.

Orchestrates the 4-agent pipeline sequentially, passing context between agents:
  FigmaFetch → DesignAnalyzer → ComponentPlanner → CodeGenerator → CodeReviewer

Uses Agno's sequential workflow pattern (not Team API, which is for collaborative
agents), giving precise control over data flow and intermediate results.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from agents.design_analyzer import create_design_analyzer_agent
from agents.component_planner import create_component_planner_agent
from agents.code_generator import create_code_generator_agent
from agents.code_reviewer import create_code_reviewer_agent
from figma_client import FigmaClient
from figma_parser import FigmaParser
from react_generator import ReactGenerator

console = Console()


def _extract_json(text: str) -> dict | list:
    """
    Robustly extracts JSON from an LLM response.
    Handles markdown code fences, leading text, and whitespace.
    """
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\n?", "", text).strip()
    text = text.strip("`").strip()

    # Try full text first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON by brackets
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not extract valid JSON from LLM response:\n{text[:500]}")


def run_figma_to_react_pipeline(
    figma_url: str,
    output_dir: str = "./generated",
    node_id: str | None = None,
) -> dict[str, Any]:
    """
    Main pipeline: converts a Figma URL to React components.

    Args:
        figma_url:   Full Figma file URL
        output_dir:  Directory to write generated files
        node_id:     Optional specific node/frame to convert

    Returns:
        Summary dict with generated files and quality reports.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "figma_url": figma_url,
        "output_dir": str(output_path.resolve()),
        "components_generated": [],
        "errors": [],
    }

    # ── Step 1: Fetch Figma Data ───────────────────────────────────────────────
    with console.status("[bold cyan]📡 Fetching Figma design...", spinner="dots"):
        client = FigmaClient()
        file_key, parsed_node_id = FigmaClient.parse_figma_url(figma_url)
        target_node = node_id or parsed_node_id

        console.print(f"  [dim]File key: {file_key}[/dim]")

        figma_json = client.get_file(file_key)
        console.print(f"  [green]✓[/green] Fetched: [bold]{figma_json.get('name', 'Untitled')}[/bold]")

    # ── Step 2: Parse Figma JSON ───────────────────────────────────────────────
    with console.status("[bold cyan]🔍 Parsing design structure...", spinner="dots"):
        parser = FigmaParser()
        parsed_design = parser.parse_file(figma_json, target_node_id=target_node)
        console.print(
            f"  [green]✓[/green] Parsed {len(parsed_design.root_nodes)} top-level components"
        )
        console.print(
            f"  [dim]Design tokens: {len(parsed_design.tokens.colors)} colors, "
            f"{len(parsed_design.tokens.font_families)} font families[/dim]"
        )

    # ── Step 3: Design Analysis (Agent 1) ─────────────────────────────────────
    console.rule("[bold blue]Agent 1: Design Analyzer[/bold blue]")
    design_analyzer = create_design_analyzer_agent()

    design_data_json = json.dumps(
        {
            "file_name": parsed_design.file_name,
            "design_tokens": parsed_design.tokens.to_dict(),
            "components": [node.to_dict() for node in parsed_design.root_nodes],
        },
        indent=2,
    )

    with console.status("[cyan]Analyzing design...[/cyan]", spinner="dots"):
        analyzer_response = design_analyzer.run(
            f"Analyze this Figma design data and return the structured JSON analysis:\n\n{design_data_json}"
        )

    try:
        design_analysis = _extract_json(analyzer_response.content)
        console.print(f"  [green]✓[/green] Analysis complete. "
                      f"Found {len(design_analysis.get('components', []))} components.")
    except ValueError as e:
        console.print(f"  [yellow]⚠ Warning:[/yellow] Could not parse analyzer response. Using raw data.")
        design_analysis = {"components": [], "raw_response": analyzer_response.content}

    # ── Step 4: Component Planning (Agent 2) ──────────────────────────────────
    console.rule("[bold blue]Agent 2: Component Planner[/bold blue]")
    component_planner = create_component_planner_agent()

    with console.status("[cyan]Planning component architecture...[/cyan]", spinner="dots"):
        planner_response = component_planner.run(
            f"Create a React component plan for this design analysis:\n\n"
            f"{json.dumps(design_analysis, indent=2)}"
        )

    try:
        component_plan = _extract_json(planner_response.content)
        components_to_generate = component_plan.get("components", [])
        generation_order = component_plan.get("generation_order", [
            c.get("component_name", c.get("file_name", "Unknown"))
            for c in components_to_generate
        ])
        console.print(
            f"  [green]✓[/green] Planned {len(components_to_generate)} components: "
            f"{', '.join(generation_order)}"
        )
    except ValueError:
        console.print("  [yellow]⚠ Warning:[/yellow] Could not parse planner response.")
        component_plan = {"components": []}
        components_to_generate = []

    # Write global CSS variables file
    generator = ReactGenerator(output_path)
    tokens_css = parsed_design.tokens.to_css_variables()
    generator.write_file("tokens.css", tokens_css)
    console.print("  [dim]→ Wrote tokens.css[/dim]")

    # ── Step 5 & 6: Code Generation + Review (Agents 3 & 4) ──────────────────
    code_generator = create_code_generator_agent()
    code_reviewer = create_code_reviewer_agent()

    for component_spec in components_to_generate:
        comp_name = component_spec.get("component_name", "UnknownComponent")
        console.rule(f"[bold blue]Generating: {comp_name}[/bold blue]")

        try:
            # Agent 3: Generate code
            with console.status(f"[cyan]Generating {comp_name}...[/cyan]", spinner="dots"):
                gen_prompt = (
                    f"Design Analysis:\n{json.dumps(design_analysis, indent=2)}\n\n"
                    f"Component Plan (full):\n{json.dumps(component_plan, indent=2)}\n\n"
                    f"Generate THIS specific component:\n{json.dumps(component_spec, indent=2)}"
                )
                gen_response = code_generator.run(gen_prompt)

            generated_code = _extract_json(gen_response.content)
            console.print(f"  [green]✓[/green] Code generated for {comp_name}")

            # Agent 4: Review & correct code
            with console.status(f"[cyan]Reviewing {comp_name}...[/cyan]", spinner="dots"):
                review_prompt = (
                    f"Design Analysis (source of truth):\n{json.dumps(design_analysis, indent=2)}\n\n"
                    f"Generated Code to Review:\n{json.dumps(generated_code, indent=2)}"
                )
                review_response = code_reviewer.run(review_prompt)

            reviewed_code = _extract_json(review_response.content)
            quality_score = reviewed_code.get("quality_score", "N/A")
            issues = reviewed_code.get("issues_found", [])
            criticals = [i for i in issues if i.get("severity") == "critical"]

            console.print(
                f"  [green]✓[/green] Review complete. "
                f"Quality: [bold]{quality_score}/10[/bold]. "
                f"Issues fixed: {len(issues)} "
                f"([red]{len(criticals)} critical[/red])"
            )

            # Write files
            tsx_info = reviewed_code.get("tsx_file") or generated_code.get("tsx_file", {})
            css_info = reviewed_code.get("css_file") or generated_code.get("css_file", {})

            tsx_path = generator.write_file(
                tsx_info.get("file_name", f"{comp_name}.tsx"),
                tsx_info.get("content", "// Generation failed"),
            )
            css_path = generator.write_file(
                css_info.get("file_name", f"{comp_name}.module.css"),
                css_info.get("content", "/* Generation failed */"),
            )

            console.print(f"  [dim]→ Wrote: {tsx_info.get('file_name')}[/dim]")
            console.print(f"  [dim]→ Wrote: {css_info.get('file_name')}[/dim]")

            summary["components_generated"].append({
                "name": comp_name,
                "tsx_file": tsx_info.get("file_name"),
                "css_file": css_info.get("file_name"),
                "quality_score": quality_score,
                "issues": issues,
            })

        except Exception as e:
            error_msg = f"Failed to generate {comp_name}: {e}"
            console.print(f"  [red]✗ {error_msg}[/red]")
            summary["errors"].append(error_msg)

    # ── Generate index.ts barrel ──────────────────────────────────────────────
    if summary["components_generated"]:
        index_content = "\n".join(
            f"export {{ default as {c['name']} }} from './{c['tsx_file'].replace('.tsx', '')}';"
            for c in summary["components_generated"]
            if c.get("tsx_file")
        )
        generator.write_file("index.ts", index_content)
        console.print("\n  [dim]→ Wrote: index.ts (barrel exports)[/dim]")

    return summary
