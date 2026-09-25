# AI Agent Integration Guide

`codeui` is specifically architected as a companion library and context builder for LLM AI coding agents, subagents, and automated developer tools.

Repository: [https://github.com/AAlsubari/codeUI](https://github.com/AAlsubari/codeUI)

---

## 1. Zero Token Counting Context Generation

Traditional LLM coding tools attempt to manage context by counting tokens and truncating text buffers. `codeui` eliminates token counting entirely:

1. **AST Graph Traversal**: `codeui` parses source files into a frozen intermediate representation graph of symbols and directed relationship edges (`calls`, `imports`, `defines`, `uses`).
2. **Dynamic Depth Bounding**: Context scope is determined purely by graph traversal distance (depth `d=1`, `d=2`, etc.) centered on target symbols or files.
3. **Compact Subgraph Context Bundles**: `ContextBuilder` outputs JSON bundles containing target bodies, cross-module signatures, detected defect findings, and minimal structural relationship edges.

---

## 2. Dual-Mode Editing (Direct Disk vs. Non-Destructive Overrides)

`codeui` supports two distinct editing paradigms via `EditTools`:

### Mode A: Direct Disk Edit Mode (`direct_disk=True`)
When developers or AI agents run `codeui` programmatically, via CLI, or with the UI "Direct Disk Edit" toggle enabled, file edits write directly to physical files on disk.

```python
tools = EditTools(graph, store, project_root=Path("."), direct_disk=True)
proposal = tools.replace_file("src/utils.py", new_code)
saved_path = tools.apply_to_disk(proposal)
```

### Mode B: Non-destructive Shadow Edit Mode (`direct_disk=False`)
In interactive exploration sessions, AI agents can propose experimental edits non-destructively into `OverrideStore`. Changes are stored in memory without mutating disk files and can be rendered as unified diffs (`store.to_diff()`).

---

## 3. Automated Agent Contribution & Self-Healing Workflow

When an AI agent uses `codeui` and discovers a bug, missing analyzer rule, or performance bottleneck in `codeui` itself, it can automatically contribute a fix back to the official repository:

```
[ AI Agent Uses codeui ]
          │
  (Discovers Bug / Suggestion)
          │
          ▼
[ ContributionManager ]
          │
  1. Fetch Repo URL (https://github.com/AAlsubari/codeUI)
  2. Clone repo to isolated temp environment
  3. Create feature branch (agent/fix-<title-slug>)
  4. Apply modified files & validate build
  5. Commit & Push to GitHub repository
```

### Python Agent Code Example:

```python
from codeui.agent.contribution import ContributionManager

manager = ContributionManager(token=github_token)
result = manager.submit_contribution(
    title="Fix circular dependency detection false positive",
    description="Refined SCC node filtering for self-referencing imports.",
    file_changes={"codeui/analysis/circular.py": updated_circular_code},
    push=True,
)
```

### Server API Endpoint:

AI agents interacting over HTTP with a `codeui` server can submit contributions via REST API:

```http
POST /api/v1/agent/contribute
Content-Type: application/json

{
  "title": "Agent bug fix",
  "description": "Fixes parser error on async generators",
  "file_changes": {
    "codeui/lang/python.py": "# fixed code"
  },
  "push": true
}
```

---

## 4. Model Context Protocol (MCP) Integration

`codeui` provides server primitives and tools that integrate seamlessly into MCP servers or agent tool registries, allowing LLMs to invoke `scan`, `trace`, `context`, `defects`, `apply`, and `contribute` as agent tools.
