# 🎨 Figma → React Converter Agent

A **robust, multi-agent AI system** that converts Figma designs into production-ready **React TypeScript** components. Built on the [Agno framework](https://agno.com) using `minimax/minimax-m2.5:free` via OpenRouter (swappable to Ollama in one config line).

---

## Architecture

```
Figma URL
    │
    ▼
[FigmaClient] → Fetch raw JSON via Figma REST API
    │
    ▼
[FigmaParser] → Normalize to typed DesignNode tree + DesignTokens
    │
    ▼
[Agent 1: DesignAnalyzerAgent]  — Extracts layout, colors, typography, spacing
    │
    ▼
[Agent 2: ComponentPlannerAgent] — Plans React component hierarchy + TypeScript props
    │
    ▼
[Agent 3: CodeGeneratorAgent]   — Generates pixel-perfect TSX + CSS Modules
    │
    ▼
[Agent 4: CodeReviewerAgent]    — Reviews & self-corrects code (a11y, TS, style accuracy)
    │
    ▼
/generated/
  tokens.css          ← Design tokens as CSS custom properties
  ComponentA.tsx
  ComponentA.module.css
  ComponentB.tsx
  ...
  index.ts            ← Barrel exports
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- A [Figma Personal Access Token](https://www.figma.com/developers/api#access-tokens)
- An [OpenRouter API Key](https://openrouter.ai) (free tier works with minimax-m2.5:free)

### 2. Install

```powershell
cd figma_react_agent
pip install -r requirements.txt
```

### 3. Configure

```powershell
copy .env.example .env
# Edit .env and add:
# FIGMA_ACCESS_TOKEN=figd_...
# OPENROUTER_API_KEY=sk-or-...
```

### 4. Run

```powershell
# Convert entire Figma file
python main.py --url "https://www.figma.com/file/YOUR_FILE_KEY/Design-Name"

# Convert a specific frame/component (use node-id from Figma URL)
python main.py --url "https://www.figma.com/file/ABC/Design?node-id=1-23" --output ./my-components

# Override token inline
python main.py --url "..." --token "figd_abc..." --output ./out

# Save full agent analysis for debugging
python main.py --url "..." --save-analysis
```

---

## Switching to Ollama (Local LLM)

Edit `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

That's it — **zero code changes needed**.

---

## Output Structure

```
generated/
├── tokens.css              # :root { --color-*: #hex; --spacing-*: Npx; ... }
├── Button.tsx              # React TSX component
├── Button.module.css       # CSS Module (pixel-perfect from Figma)
├── HeroSection.tsx
├── HeroSection.module.css
└── index.ts                # export { default as Button } from './Button'
```

Each component features:
- ✅ TypeScript with strict props interface
- ✅ CSS Modules (no inline styles for static values)
- ✅ Semantic HTML (`<button>`, `<nav>`, `<header>`, etc.)
- ✅ ARIA accessibility attributes
- ✅ Keyboard navigation
- ✅ Responsive breakpoints (768px, 1024px)
- ✅ Pixel-accurate dimensions, colors, typography from Figma

---

## Project Structure

```
figma_react_agent/
├── main.py                    # CLI entry point
├── config.py                  # LLM provider switching
├── figma_client.py            # Figma REST API wrapper
├── figma_parser.py            # Figma JSON → typed dataclasses
├── react_generator.py         # File writing utilities
├── agents/
│   ├── design_analyzer.py     # Agent 1: Analyze design
│   ├── component_planner.py   # Agent 2: Plan components
│   ├── code_generator.py      # Agent 3: Generate code
│   ├── code_reviewer.py       # Agent 4: Review & correct
│   └── team.py                # Pipeline orchestrator
├── tools/
│   ├── figma_tools.py         # Agno tool wrappers for Figma
│   └── code_tools.py          # Code utilities (naming, validation)
├── test_parser.py             # Unit tests
├── requirements.txt
├── .env.example
└── generated/                 # Output (gitignored)
```

---

## Running Tests

```powershell
pip install pytest
python -m pytest test_parser.py -v
```

---

## Tips for Best Results

1. **Name your layers**: Use descriptive names in Figma (e.g., `HeroSection`, `PrimaryButton`) — agents use these as component names.
2. **Use Auto Layout**: Figma auto-layout maps cleanly to CSS flexbox. Components without auto-layout get `position: absolute`.
3. **Use Variables/Styles**: Define color and text styles in Figma — they become CSS custom properties.
4. **Target specific nodes**: Use `--node-id` to convert a single component rather than a full page (saves tokens and time).
5. **Inspect quality scores**: The `CodeReviewerAgent` gives each component a 1–10 score. Scores below 7 indicate issues to check.

---

## Supported Figma URL Formats

| Format | Example |
|---|---|
| Standard file | `figma.com/file/<key>/Title` |
| Design URL | `figma.com/design/<key>/Title` |
| With node-id | `figma.com/file/<key>/Title?node-id=1-23` |
| Community file | `figma.com/community/file/<key>` |
