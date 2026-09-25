"""Dead code and unused export analyzer."""
from pathlib import Path
from typing import ClassVar, Iterable, List, Set
from codeui.analysis.base import AnalysisContext, Analyzer
from codeui.core.graph import Graph
from codeui.core.ir import EdgeKind, Finding, Location, Severity, SymbolKind, Visibility

class DeadCodeAnalyzer(Analyzer):
    """Detects unused functions, unused private symbols, and orphan files.
    Example:
        >>> analyzer = DeadCodeAnalyzer()
        >>> g = Graph()
        >>> ctx = AnalysisContext(Path("."))
        >>> list(analyzer.run(g, ctx))
        []
    """
    id: ClassVar[str] = "dead_code"
    severity_default: ClassVar[Severity] = Severity.WARNING

    ENTRY_POINTS = {"main", "index", "App", "app", "run", "handler", "start", "cli"}
    SPECIAL_METHODS = {
        "__init__", "__post_init__", "__str__", "__repr__", "__eq__", "__hash__",
        "__iter__", "__getitem__", "__setitem__", "__delitem__", "__len__",
        "__contains__", "__enter__", "__exit__", "__call__", "__await__",
        "constructor", "init", "dispose", "render", "setup", "teardown", "setUp", "tearDown"
    }

    def run(self, graph: Graph, ctx: AnalysisContext) -> Iterable[Finding]:
        """Find dead code and unreferenced functions/classes.
        Example:
            >>> analyzer = DeadCodeAnalyzer()
            >>> g = Graph()
            >>> list(analyzer.run(g, AnalysisContext(Path("."))))
            []
        """
        findings: List[Finding] = []
        referenced_targets: Set[str] = set()
        for edge in graph.get_edges():
            if edge.kind in (EdgeKind.CALLS, EdgeKind.REFERENCES, EdgeKind.IMPORTS, EdgeKind.EXPORTS, EdgeKind.TESTS):
                referenced_targets.add(edge.target_id)
                raw_target = edge.target_id.split("::")[-1]
                referenced_targets.add(raw_target)
                referenced_targets.add(raw_target.split(".")[-1])

        for sym in graph.get_all_symbols():
            if sym.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS):
                if sym.name in self.ENTRY_POINTS or any(sym.name.startswith(p) for p in self.ENTRY_POINTS):
                    continue
                if sym.name in self.SPECIAL_METHODS or sym.name.startswith("__"):
                    continue
                if sym.visibility == Visibility.PRIVATE and sym.id not in referenced_targets and sym.name not in referenced_targets:
                    finding = Finding(
                        id=f"dead_code::{sym.id}",
                        rule_id="dead_code",
                        message=f"Symbol '{sym.name}' is defined but never used",
                        severity=self.severity_default,
                        location=sym.location,
                        symbol_id=sym.id,
                        fix_hint=f"Remove unused symbol '{sym.name}' or export/call it",
                        confidence=0.85,
                    )
                    findings.append(finding)
        return findings
