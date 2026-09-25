# Contributing to codeui

Thank you for your interest in contributing to `codeui`! Whether you are a human developer or an AI agent, we welcome contributions that improve static analysis accuracy, performance, multi-language support, defect detectors, and context tools.

Repository: [https://github.com/AAlsubari/codeUI](https://github.com/AAlsubari/codeUI)

---

## Core Engineering Rules

When contributing code to `codeui`, you MUST adhere to the following core engineering rules:

1. **Static Analysis Only**: NEVER `exec`, `eval`, or `import` analyzed user code.
2. **Rule 6 — Zero Source Comments**: NO inline comments (`#`) inside `src/codeui/` library source code files. Docstrings on public interfaces are allowed and encouraged. Clear function naming and concise logic must self-document the code.
3. **Public Interface Docstrings**: All public functions and classes must include complete docstrings with runnable `doctest` examples.
4. **Typed Exceptions**: All error paths must raise typed exceptions derived from `codeui.errors.CodeUIError`.
5. **Direct Disk & Override Compatibility**: Maintain dual-mode support for non-destructive `OverrideStore` shadow edits and direct disk project file writes.
6. **No Token Counting**: Do not introduce tokenizers or token counting dependencies. Use graph traversal depth to determine context bounds.

---

## Local Development Setup

Clone the repository and set up a development virtual environment:

```bash
git clone https://github.com/AAlsubari/codeUI.git
cd codeUI
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Running Tests & Verification

Before submitting changes, ensure all unit tests, doctests, and type checks pass cleanly:

```bash
# Run pytest with coverage
pytest --cov=src/codeui

# Run doctests across module source files
python3 -m pytest --doctest-modules src/codeui

# Run type checker
mypy --strict src/codeui
```

---

## Automated Contributions for AI Agents

`codeui` features an integrated contribution pipeline for AI agents (`codeui.agent.contribution.ContributionManager`):

When an AI agent identifies bugs, missing features, or improvements while using `codeui`, it can automatically clone the repository, apply changes, and push a contribution:

```bash
codeui contribute \
  --title "Fix Python AST async generator symbol extraction" \
  --description "Resolves issue where async generators lacked proper SymbolKind classification." \
  --file "codeui/lang/python.py" "$(cat updated_python.py)" \
  --token "$GITHUB_TOKEN"
```

Programmatic API for agents:

```python
from codeui.agent.contribution import ContributionManager

mgr = ContributionManager()
result = mgr.submit_contribution(
    title="Fix AST parser edge case",
    description="Detailed description of fix.",
    file_changes={"codeui/lang/python.py": "updated_content"},
    push=True
)
```

---

## Pull Request Guidelines

1. **Branch Naming**: Use descriptive branch names like `feature/ast-go-enhancements` or `bugfix/circular-dependency-solver` (agents automatically use `agent/<slug>`).
2. **Commit Messages**: Write concise, imperative commit messages (e.g., `Add Rust language adapter for trait declarations`).
3. **Test Coverage**: Ensure all new functionality includes test cases in `tests/`.

---

## License

By contributing to `codeui`, you agree that your contributions will be licensed under the project's [MIT License](./LICENSE).
