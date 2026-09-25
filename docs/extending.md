# Extending codeui

`codeui` is architected for extensibility. You can create custom language adapters, custom defect analysis rules, custom report emitters, or custom agent tools.

Repository: [https://github.com/AAlsubari/codeUI](https://github.com/AAlsubari/codeUI)

---

## 1. Custom Language Adapters

To add support for a new programming language, subclass `LanguageAnalyzer` and register your class with `LanguageRegistry`:

```python
from pathlib import Path
from typing import Iterator, Sequence
from codeui.lang.base import LanguageAnalyzer, ParseResult
from codeui.core.ir import Symbol, Edge, SymbolKind, Visibility, Location
from codeui.lang.registry import LanguageRegistry

class CustomLangAnalyzer(LanguageAnalyzer):
    language = "custom"
    extensions = (".custom", ".cst")

    def parse(self, path: Path, source: str) -> ParseResult:
        # Implement static AST parsing here
        return ParseResult(ast_tree={}, source=source, path=path)

    def extract_symbols(self, parse_res: ParseResult) -> Iterator[Symbol]:
        # Yield extracted Symbol objects
        yield Symbol(
            id=f"{parse_res.path}::main",
            name="main",
            kind=SymbolKind.FUNCTION,
            visibility=Visibility.PUBLIC,
            location=Location(file_id=str(parse_res.path), start_line=1, start_col=0, end_line=10, end_col=0)
        )

    def extract_edges(self, parse_res: ParseResult, symbols: Sequence[Symbol]) -> Iterator[Edge]:
        # Yield extracted Edge objects
        return iter([])

# Register custom language analyzer
LanguageRegistry().register(CustomLangAnalyzer())
```

---

## 2. Custom Defect Analyzers

To write a custom defect rule, implement the `BaseAnalyzer` interface and register it in `AnalysisRunner`:

```python
from typing import List
from codeui.analysis.base import BaseAnalyzer, AnalysisContext
from codeui.core.graph import Graph
from codeui.core.ir import Finding, Severity, Location

class MaxFunctionLengthRule(BaseAnalyzer):
    rule_id = "max_function_length"

    def analyze(self, graph: Graph, ctx: AnalysisContext) -> List[Finding]:
        findings = []
        for symbol in graph.get_all_symbols().values():
            if symbol.location and (symbol.location.end_line - symbol.location.start_line > 100):
                findings.append(Finding(
                    rule_id=self.rule_id,
                    message=f"Function '{symbol.name}' exceeds 100 lines limit.",
                    severity=Severity.WARNING,
                    location=symbol.location
                ))
        return findings
```

---

## 3. Plugin Registration via Setuptools Entry Points

Plugins can be packaged as standalone Python packages and registered automatically via `pyproject.toml` or `setup.py` entry points:

```toml
[project.entry-points."codeui.plugins"]
my_custom_plugin = "my_package.plugin:register"
```
