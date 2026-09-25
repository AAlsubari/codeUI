# Python API Reference

The `codeui` package exposes a clean Python API for programmatically building code graphs, tracing symbol dependencies, running static defect checks, building AI agent context bundles, applying file edits, and managing repository contributions.

Repository: [https://github.com/AAlsubari/codeUI](https://github.com/AAlsubari/codeUI)

---

## Core Classes & Functions

### `codeui.cli.main.scan_project`

Scans a directory or remote Git repository and returns a populated `Graph`.

```python
from pathlib import Path
from codeui.cli.main import scan_project

graph = scan_project(
    project_path=Path("."),
    entry_points=["src/main.py"],
    layer_rules={"frontend": ["src/ui/*"], "backend": ["src/api/*"]}
)
```

- **Parameters**:
  - `project_path`: `Union[str, Path]` — Root directory or git clone URL.
  - `entry_points`: `Optional[Sequence[str]]` — Explicit entry points.
  - `layer_rules`: `Optional[Dict[str, Any]]` — Architectural layer rules.
- **Returns**: `codeui.core.graph.Graph`

---

### `codeui.core.graph.Graph`

The universal graph store holding extracted symbols, directed edges, and detected findings.

```python
# Access graph elements
symbols = graph.get_all_symbols()      # Dict[str, Symbol]
edges = graph.get_all_edges()          # List[Edge]
findings = graph.get_findings()        # List[Finding]
files = graph.get_all_files()          # Set[str]

# Query specific symbol
symbol = graph.get_symbol("src/main.py::run")
```

---

### `codeui.tracer.tracer.Tracer`

Performs depth-bounded graph traversals for call hierarchies and dependency trees.

```python
from codeui.tracer.tracer import Tracer

tracer = Tracer(graph)

# Forward trace (what target calls)
called_symbols = list(tracer.forward("src/main.py::run", depth=3))

# Backward trace (who calls target)
callers = list(tracer.backward("src/db.py::connect", depth=3))
```

---

### `codeui.agent.context.ContextBuilder`

Constructs dynamic, compact context bundles for LLM prompts.

```python
from codeui.agent.context import ContextBuilder, TaskSpec

builder = ContextBuilder(graph)

# Context bundle for symbol
bundle = builder.for_symbol("src/main.py::run", depth=2)

# Context bundle for task specification
task = TaskSpec(query="Fix memory leak", target_files=["src/main.py"])
task_bundle = builder.for_task(task, depth=1)

# Serialize to JSON
json_payload = bundle.to_json()
```

---

### `codeui.agent.edit_tools.EditTools` & `OverrideStore`

Provides dual-mode file modification: non-destructive shadow edits in `OverrideStore` or direct writes to project files on disk.

```python
from codeui.core.override import OverrideStore
from codeui.agent.edit_tools import EditTools

store = OverrideStore()

# Direct Disk Edit Mode
tools_disk = EditTools(graph, store, project_root=Path("."), direct_disk=True)
proposal = tools_disk.replace_file("src/config.py", "DEBUG = True\n")
written_path = tools_disk.apply_to_disk(proposal)

# Non-destructive Shadow Edit Mode
tools_shadow = EditTools(graph, store, project_root=Path("."), direct_disk=False)
shadow_prop = tools_shadow.replace_file("src/config.py", "DEBUG = False\n")
tools_shadow.apply(shadow_prop, write_to_disk=False)

# Get unified diff of shadow overrides
diff_text = store.to_diff()
```

---

### `codeui.agent.contribution.ContributionManager`

Enables AI agents to dynamically fetch repository metadata, clone `https://github.com/AAlsubari/codeUI`, create feature branches, commit improvements, and push contributions.

```python
from codeui.agent.contribution import ContributionManager
from codeui.core.repo import get_library_repo_url

print("Target Repository:", get_library_repo_url())

mgr = ContributionManager(token="optional_github_token")
result = mgr.submit_contribution(
    title="Fix parser edge case in Python analyzer",
    description="Improves AST handling for nested async function definitions.",
    file_changes={"codeui/lang/python.py": "# new parser content"},
    branch_name="agent/fix-python-ast-nested-async",
    push=True,
)

print(result["status"])  # 'success'
```

---

### `codeui.core.repo.get_library_repo_url`

Returns the official `codeui` GitHub repository URL (`https://github.com/AAlsubari/codeUI`) or custom environment override (`CODEUI_GITHUB_REPO_URL`).

```python
from codeui.core.repo import get_library_repo_url

repo_url = get_library_repo_url()
# Returns: "https://github.com/AAlsubari/codeUI"
```
