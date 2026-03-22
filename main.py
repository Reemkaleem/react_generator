"""
main.py — CLI entry point for the Figma → React Converter Agent.

Usage:
    python main.py --url "https://www.figma.com/file/ABC123/MyDesign"
    python main.py --url "..." --output ./my-components --node-id "1:23"
    python main.py --url "..." --output ./out --provider ollama
"""

from __future__ import annotations

import sys
import argparse
import json
import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config import (
    validate_config,
    LLM_PROVIDER,
    OPENROUTER_MODEL,
    OLLAMA_MODEL,
    resolve_openrouter_model,
)

console = Console()

BANNER = """
╔═══════════════════════════════════════════════════════════╗
║         🎨  Figma → React Converter Agent                ║
║              Powered by Agno Framework                    ║
╚═══════════════════════════════════════════════════════════╝"""


def print_banner():
    console.print(Text(BANNER, style="bold magenta"))
    model_warning = None
    if LLM_PROVIDER == "openrouter":
        model_name, model_warning = resolve_openrouter_model()
    else:
        model_name = OLLAMA_MODEL

    console.print(
        f"  Provider: [bold cyan]{LLM_PROVIDER.upper()}[/bold cyan]  "
        f"Model: [bold yellow]{model_name}[/bold yellow]\n"
    )
    if model_warning:
        console.print(f"  [yellow]⚠ {model_warning}[/yellow]")
        console.print()


def print_summary(summary: dict):
    """Prints a rich summary table of generated components."""
    console.print()
    console.rule("[bold green]✅ Generation Complete[/bold green]")
    console.print()

    table = Table(title="Generated Components", show_header=True, header_style="bold cyan")
    table.add_column("Component", style="bold")
    table.add_column("TSX File")
    table.add_column("CSS File")
    table.add_column("Quality")
    table.add_column("Issues")

    for comp in summary.get("components_generated", []):
        score = comp.get("quality_score", "?")
        score_color = "green" if isinstance(score, int) and score >= 8 else "yellow"
        issues = comp.get("issues", [])
        criticals = sum(1 for i in issues if i.get("severity") == "critical")
        warnings = sum(1 for i in issues if i.get("severity") == "warning")

        table.add_row(
            comp.get("name", "Unknown"),
            comp.get("tsx_file", "-"),
            comp.get("css_file", "-"),
            f"[{score_color}]{score}/10[/{score_color}]",
            f"[red]{criticals} crit[/red] / [yellow]{warnings} warn[/yellow]",
        )

    console.print(table)

    if summary.get("errors"):
        console.print("\n[bold red]Errors:[/bold red]")
        for err in summary["errors"]:
            console.print(f"  [red]• {err}[/red]")

    output_dir = summary.get("output_dir", "./generated")
    console.print(
        f"\n[bold green]Output directory:[/bold green] {output_dir}"
    )
    console.print(
        f"Total components: [bold]{len(summary.get('components_generated', []))}[/bold]\n"
    )


def main():
    parser = argparse.ArgumentParser(
        description="🎨 Figma → React Converter Agent (Powered by Agno)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --url "https://www.figma.com/file/ABC/Design"
  python main.py --url "https://www.figma.com/file/ABC/Design?node-id=1%3A23" --output ./components
  python main.py --url "..." --token "figd_abc..." --output ./out
        """,
    )

    parser.add_argument(
        "--url", "-u",
        required=True,
        help="Figma file URL (supports file, design, and community URLs)",
    )
    parser.add_argument(
        "--output", "-o",
        default="./generated",
        help="Output directory for generated React files (default: ./generated)",
    )
    parser.add_argument(
        "--node-id", "-n",
        default=None,
        help="Optional: Specific Figma node ID to convert (e.g., '1:23')",
    )
    parser.add_argument(
        "--token", "-t",
        default=None,
        help="Figma Personal Access Token (overrides FIGMA_ACCESS_TOKEN env var)",
    )
    parser.add_argument(
        "--provider",
        choices=["openrouter", "ollama"],
        default=None,
        help="LLM provider override (overrides LLM_PROVIDER env var)",
    )
    parser.add_argument(
        "--save-analysis",
        action="store_true",
        help="Save intermediate design analysis JSON to output directory",
    )

    args = parser.parse_args()

    # Apply CLI overrides to environment
    if args.token:
        os.environ["FIGMA_ACCESS_TOKEN"] = args.token
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    print_banner()

    # Validate configuration before starting
    try:
        validate_config()
    except EnvironmentError as e:
        console.print(f"[bold red]Configuration Error:[/bold red]\n{e}")
        console.print(
            "\n[dim]Tip: Copy .env.example to .env and fill in your API keys.[/dim]"
        )
        sys.exit(1)

    # Run the pipeline
    try:
        from agents.team import run_figma_to_react_pipeline

        summary = run_figma_to_react_pipeline(
            figma_url=args.url,
            output_dir=args.output,
            node_id=args.node_id,
        )
        print_summary(summary)

        # Optionally save summary
        if args.save_analysis:
            summary_path = Path(args.output) / "_agent_summary.json"
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            console.print(f"[dim]Agent summary saved to: {summary_path}[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Interrupted by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Fatal error:[/bold red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
