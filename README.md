# codeui-python 🌐⚡

[![PyPI Version](https://img.shields.io/pypi/v/codeui-python.svg)](https://pypi.org/project/codeui-python/)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style](https://img.shields.io/badge/code%20style-strict-green.svg)](https://github.com/AAlsubari/codeUI)

**`codeui-python`** (`codeui`) is an open-source static analysis engine that converts any Python or polyglot software repository into a rich, **interactive web graph visualizer**, call-hierarchy tracer, defect detector, live code editor, and AI agent context builder.

It safely parses codebases via AST (Abstract Syntax Tree) without ever executing or importing target code, producing a universal intermediate representation (IR) graph.

📦 **PyPI Package**: [https://pypi.org/project/codeui-python/](https://pypi.org/project/codeui-python/)  
🐙 **GitHub Repository**: [https://github.com/AAlsubari/codeUI](https://github.com/AAlsubari/codeUI)

---

## 🌟 Main Features

### 1. 🕸️ Convert Any Project into an Interactive Graph
Effortlessly explore your entire codebase as a force-directed, interactive visual dependency graph:
- **Universal AST Parsing**: Maps modules, classes, functions, variables, imports, and calls across Python, TypeScript, Go, Rust, Java, .etc.
- **Multi-Window Subgraph Workspaces**: Open symbols, modules, and call chains in floating, draggable windows.
- **Cross-Usage Navigation**: Trace incoming/outgoing references across files in real time.

### 2. 📝 Interactive Code Editor & Live Edits
Edit and refactor code directly inside the graph UI (`http://127.0.0.1:3000`):
- **Direct Disk Writing**: Save edits directly to your local source files on disk with a single click.
- **In-Memory Shadow Overrides**: Test edits non-destructively in an in-memory shadow store with instant diff inspection before writing to disk.

### 3. 🔍 Static Defect Detection Engine
Includes 8 built-in static defect analyzers that identify structural code bugs before runtime:
- `undefined`: Missing or undefined symbols and functions.
- `dead_code`: Unreferenced private functions and unused module exports.
- `unresolved_import`: Broken or unresolvable import statements.
- `circular`: Cyclic dependency chains via Tarjan's Strongly Connected Components algorithm.
- `duplicates`: Structural code clones and duplicate routines.
- `unreachable`: Code paths following terminal control statements (`return`, `raise`, `exit`).
- `shadowing`: Variable shadowing across nested lexical scopes.
- `api_drift`: Public API signature changes and breaking contract drift against baseline snapshots.

### 4. 🤖 AI Agent Context Engine 
- **Smart Subgraph Bundling**: Extracts minimal, context-complete subgraphs for LLMs (Claude, GPT-4, Gemini) without token bloat.


---

## ⚠️ Initial Release Notice & Call for Contributions

> **Note on Version 0.1.1**:  
> `codeui-python` is currently in an **initial pre-release version**. Static analysis across complex, dynamic multi-language codebases is intricate, and you may encounter bugs, unparsed syntax edge cases, or unsupported language features.
>
> 🚀 **We Welcome All Contributions!**  
> We actively invite developers, researchers, and open-source contributors to try `codeui-python`, report issues, submit feature requests, or open pull requests to help expand language support and parser capabilities.

---

## 📦 Installation

Install the library via PyPI:

```bash
pip install codeui-python
```

Or install the development version from source:

```bash
git clone https://github.com/AAlsubari/codeUI.git
cd codeUI
pip install -e ".[dev]"
```

---

## 🚀 Quickstart

### 1. Launch Interactive Graph Visualizer

Run `codeui serve` in any repository directory to open the interactive browser graph:

```bash
codeui serve . --port 3000
```

Then open `http://127.0.0.1:3000` in your browser to interactively explore, search, trace, and edit your code.

### 2. Command Line Interface (CLI)

```bash
# Scan a codebase into a JSON graph representation
codeui scan .

# Trace forward execution dependencies for a symbol
codeui trace "src/main.py::run" . --direction forward --depth 3

# Generate minimal LLM Context Bundle for AI agents
codeui context . --symbol "src/main.py::run"

# Scan codebase for defects (SARIF format)
codeui defects . --format sarif
```

### 3. Python API Usage

```python
from pathlib import Path
from codeui.cli.main import scan_project
from codeui.tracer.tracer import Tracer
from codeui.agent.context import ContextBuilder

# 1. Scan codebase into a Universal AST Graph (No code execution)
graph = scan_project(Path("."))

# 2. Perform Call Graph Tracing
tracer = Tracer(graph)
dependencies = list(tracer.forward("src/main.py::run"))

# 3. Extract LLM Context Bundle for AI Agents
builder = ContextBuilder(graph)
bundle = builder.for_symbol("src/main.py::run", depth=2)
print(bundle.to_json())
```

---

## 📚 Documentation & Resources

- [Quickstart Guide](./docs/quickstart.md)
- [Python API Reference](./docs/api.md)
- [AI Agent Integration & Context Engine](./docs/agent_integration.md)
- [Architecture Overview](./docs/architecture.md)
- [Static Analyzer & Defect Reference](./docs/analyzer_reference.md)
- [Extending codeui](./docs/extending.md)

---

## 📄 License

`codeui-python` is distributed under the [MIT License](./LICENSE). Copyright (c) 2026 Akram Alsubari and contributors.
