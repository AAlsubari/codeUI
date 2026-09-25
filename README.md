# codeui

[![PyPI Version](https://img.shields.io/pypi/v/codeui.svg)](https://pypi.org/project/codeui/)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style](https://img.shields.io/badge/code%20style-strict-green.svg)](https://github.com/AAlsubari/codeUI)

**`codeui`** is a universal, static-analysis-based code-intelligence library, defect detector, interactive graph visualizer, override store, and AI agent context builder.

It parses code bases safely without ever executing or importing analyzed code, extracting frozen intermediate representation (IR) graphs, tracing call hierarchies, detecting subtle architectural defects, and serving an interactive web visualizer.

Repository: [https://github.com/AAlsubari/codeUI](https://github.com/AAlsubari/codeUI)

---

## Key Features

- **100% Static Analysis**: Safe AST extraction — **NEVER** executes, imports, or evaluates target project code.
- **Multi-Language Adapters**: Native analyzers for Python, TypeScript, JavaScript, Go, Rust, Dockerfiles, Makefiles, and generic fallback parser.
- **Defect Detection Engine**: 8 built-in static defect analyzers:
  - `undefined`: Missing symbols and functions
  - `dead_code`: Unreferenced private routines and unused exports
  - `unresolved_import`: Missing or invalid import paths
  - `circular`: Cyclic dependency detection via Tarjan's SCC algorithm
  - `duplicates`: Structural code clone identification via shingling
  - `unreachable`: Code following terminal control statements
  - `shadowing`: Variable shadowing across nested scopes
  - `api_drift`: Interface drift tracking against baseline snapshots
- **Interactive Localhost Visualizer**: Force-directed multi-window canvas with live code editor, mini-map, symbol inspection, and direct disk edit toggle (`http://127.0.0.1:3000`).
- **Direct Disk & Non-Destructive Override Store**: Save edits live to project disk files or non-destructively in an in-memory shadow store with unified diff generation (`EditTools`, `OverrideStore`).
- **AI Agent Context Engine**: Graph-traversal based dynamic context bundling (`ContextBuilder`) optimized for LLM prompts without token counting overhead.
- **Agent Self-Contribution Workflow**: Integrated `ContributionManager` allowing AI agents to dynamically fetch repository metadata, clone `https://github.com/AAlsubari/codeUI`, apply bug fixes or feature additions, and submit contributions.

---

## Installation

Install via PyPI:

```bash
pip install codeui
```

Or install from source in editable mode:

```bash
git clone https://github.com/AAlsubari/codeUI.git
cd codeUI
pip install -e ".[dev]"
```

---

## Quickstart

### 1. Command Line Interface (CLI)

```bash
# Scan a project directory and print summary
codeui scan .

# Start the interactive visualizer server
codeui serve . --port 3000

# Perform forward symbol call trace
codeui trace "src/app.py::main" . --direction forward --depth 3

# Generate AI Agent Context Bundle for a symbol
codeui context . --symbol "src/app.py::main"

# List detected code defects in SARIF format
codeui defects . --format sarif

# Apply direct disk edit to a file
codeui apply src/main.py --content "print('hello world')" --disk

# Submit automated contribution to codeui repo
codeui contribute --title "Fix import resolution bug" --file src/fix.py "content"
```

### 2. Python API Usage

```python
from pathlib import Path
from codeui.cli.main import scan_project
from codeui.tracer.tracer import Tracer
from codeui.agent.context import ContextBuilder

# 1. Scan codebase into a Universal Graph
graph = scan_project(Path("."))

# 2. Perform Call Graph Tracing
tracer = Tracer(graph)
called_symbols = list(tracer.forward("src/main.py::run"))

# 3. Build Minimal Context Bundle for LLM Prompts
builder = ContextBuilder(graph)
bundle = builder.for_symbol("src/main.py::run", depth=2)
print(bundle.to_json())
```

---

## AI Agent Self-Improvement Workflow

`codeui` provides first-class support for AI agents to automatically improve the library when encountering bugs, missing features, or optimization opportunities:

```python
from codeui.agent.contribution import ContributionManager
from codeui.core.repo import get_library_repo_url

# Get official library repository URL (https://github.com/AAlsubari/codeUI)
repo_url = get_library_repo_url()

# Submit automated agent bug fix
mgr = ContributionManager()
result = mgr.submit_contribution(
    title="Agent: Add missing exception handling",
    description="Identified edge case in AST parser during project scan.",
    file_changes={"codeui/lang/python.py": "# fixed parser logic"},
    push=True,
)
```

---

## Code Examples

Check out the [`examples/`](./examples/) folder for complete, runnable scripts:

- [`01_basic_project_scan.py`](./examples/01_basic_project_scan.py) — Project scanning & defect detection
- [`02_symbol_tracing.py`](./examples/02_symbol_tracing.py) — Call graph forward/backward tracing
- [`03_agent_context_bundle.py`](./examples/03_agent_context_bundle.py) — LLM context bundle construction
- [`04_edits_and_overrides.py`](./examples/04_edits_and_overrides.py) — OverrideStore & direct disk edits
- [`05_agent_contribution.py`](./examples/05_agent_contribution.py) — Agent automated contribution workflow

---

## Documentation

Full documentation is available in the [`docs/`](./docs/) directory:

- [Quickstart Guide](./docs/quickstart.md)
- [Python API Reference](./docs/api.md)
- [AI Agent Integration & MCP](./docs/agent_integration.md)
- [Architecture Overview](./docs/architecture.md)
- [Static Analyzer & Defect Reference](./docs/analyzer_reference.md)
- [Extending codeui](./docs/extending.md)

---

## License

`codeui` is released under the [MIT License](./LICENSE). Copyright (c) 2026 Akram Alsubari and codeui maintainers.
