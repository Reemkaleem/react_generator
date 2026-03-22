"""
react_generator.py — File writing utilities for generated React components.

Handles writing TSX and CSS files to the output directory,
including proper formatting and directory structure.
"""

from __future__ import annotations

from pathlib import Path


class ReactGenerator:
    """Manages writing generated React files to disk."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_file(self, filename: str, content: str) -> Path:
        """
        Writes content to a file in the output directory.
        Creates subdirectories if needed (e.g., 'components/Button.tsx').
        """
        file_path = self.output_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def write_component(
        self,
        component_name: str,
        tsx_content: str,
        css_content: str,
        subdir: str = "components",
    ) -> tuple[Path, Path]:
        """
        Writes a component's TSX and CSS Module files into a subdirectory.
        Returns (tsx_path, css_path).
        """
        comp_dir = self.output_dir / subdir / component_name
        comp_dir.mkdir(parents=True, exist_ok=True)

        tsx_path = comp_dir / f"{component_name}.tsx"
        css_path = comp_dir / f"{component_name}.module.css"
        index_path = comp_dir / "index.ts"

        tsx_path.write_text(tsx_content, encoding="utf-8")
        css_path.write_text(css_content, encoding="utf-8")

        # Write a barrel index for each component folder
        index_path.write_text(
            f"export {{ default }} from './{component_name}';\n",
            encoding="utf-8",
        )

        return tsx_path, css_path

    def write_package_json(self, project_name: str = "figma-components"):
        """Writes a minimal package.json for the generated project."""
        content = f"""{{"name": "{project_name}",
  "version": "0.1.0",
  "private": true,
  "dependencies": {{
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  }},
  "devDependencies": {{
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "typescript": "^5.0.0"
  }}
}}
"""
        self.write_file("package.json", content)

    def write_tsconfig(self):
        """Writes a minimal tsconfig.json."""
        content = """{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx"
  },
  "include": ["**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
"""
        self.write_file("tsconfig.json", content)
