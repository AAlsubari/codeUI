# Quickstart Guide

This guide covers getting started with `codeui` via the Command Line Interface (CLI) and Python API.

---

## Installation

```bash
pip install codeui-python
```

---

## 1. Project Scanning

Scan a local directory or remote Git repository to construct a universal AST dependency graph:

```bash
# Scan current directory
codeui scan .

# Scan specific entry points
codeui scan . --entry src/app.py

# Output graph in JSON format
codeui scan . --json
```

---

## 2. Interactive Web Visualizer

Launch the localhost force-directed visualizer UI at `http://127.0.0.1:3000`:

```bash
codeui serve . --port 3000
```

The visualizer features multi-window canvas navigation, symbol call graph inspection, defect finding overlays, and direct disk file editing.

---

## 3. Call Graph Tracing

Trace downstream dependencies (forward) or upstream callers (backward) for any symbol ID:

```bash
# Trace forward dependencies up to depth 3
codeui trace "src/app.py::main" . --direction forward --depth 3

# Trace backward callers
codeui trace "src/db.py::connect" . --direction backward --depth 5
```

---

## 4. AI Agent Context Bundles

Generate minimal, context-complete subgraphs for LLM AI agents without token counting:

```bash
# Build context bundle around a symbol
codeui context . --symbol "src/app.py::main" --depth 2

# Build context bundle for a file
codeui context . --file "src/app.py"

# Build context bundle for a specific defect
codeui context . --defect "circular:src/a.py->src/b.py"
```

---

## 5. Defect Analysis Reports

Run all static analysis rules and output defect findings in JSON, SARIF, or Markdown:

```bash
# Export defect report in SARIF (for GitHub Code Scanning / IDEs)
codeui defects . --format sarif

# Export in Markdown
codeui defects . --format markdown
```

---

## 6. Python API Quickstart

```python
from pathlib import Path
from codeui.cli.main import scan_project
from codeui.tracer.tracer import Tracer
from codeui.agent.context import ContextBuilder

# Build Graph
graph = scan_project(Path("."))

# Trace Calls
tracer = Tracer(graph)
dependencies = list(tracer.forward("src/app.py::main"))

# Extract Agent Context Bundle
builder = ContextBuilder(graph)
bundle = builder.for_symbol("src/app.py::main", depth=2)
print(bundle.to_json())
```
