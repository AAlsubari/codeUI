# codeui Examples

This directory contains standalone Python scripts demonstrating various capabilities of the `codeui` library.

## Examples Overview

| Script | Description |
| :--- | :--- |
| `01_basic_project_scan.py` | Scan project codebases, build universal AST graph, and list detected defect findings. |
| `02_symbol_tracing.py` | Perform forward (dependency) and backward (caller) symbol traces through call graphs. |
| `03_agent_context_bundle.py` | Build compact, LLM-optimized context bundles for symbols, files, or high-level tasks. |
| `04_edits_and_overrides.py` | Use non-destructive `OverrideStore` shadow edits or direct disk edits via `EditTools`. |
| `05_agent_contribution.py` | Demonstrate AI agent self-improvement workflow: cloning `codeui` repo, applying changes, and pushing contributions. |

## Running the Examples

Ensure `codeui` is installed in your Python environment:

```bash
pip install -e .
```

Run any example script directly:

```bash
python examples/01_basic_project_scan.py
python examples/02_symbol_tracing.py
python examples/03_agent_context_bundle.py
python examples/04_edits_and_overrides.py
python examples/05_agent_contribution.py
```
