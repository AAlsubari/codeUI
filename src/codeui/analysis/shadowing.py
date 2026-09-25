"""Variable scope shadowing analyzer."""
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, List
from codeui.analysis.base import AnalysisContext, Analyzer
from codeui.core.graph import Graph
from codeui.core.ir import Finding, Location, Severity, SymbolKind

class ShadowingAnalyzer(Analyzer):
    """Detects variable shadowing across nested scopes.
    Example:
        >>> analyzer = ShadowingAnalyzer()
        >>> g = Graph()
        >>> ctx = AnalysisContext(Path("."))
        >>> list(analyzer.run(g, ctx))
        []
    """
    id: ClassVar[str] = "shadowing"
    severity_default: ClassVar[Severity] = Severity.INFO

    def run(self, graph: Graph, ctx: AnalysisContext) -> Iterable[Finding]:
        """Detect scope shadowing across inner and outer variables.
        Example:
            >>> analyzer = ShadowingAnalyzer()
            >>> g = Graph()
            >>> list(analyzer.run(g, AnalysisContext(Path("."))))
            []
        """
        findings: List[Finding] = []
        for file_path in graph.get_all_files():
            symbols = graph.get_symbols_by_file(file_path)
            scope_names: Dict[str, Any] = {}
            for s in symbols:
                if s.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.VARIABLE):
                    if s.name in scope_names and s.name not in ("__init__", "main", "_"):
                        prior = scope_names[s.name]
                        if prior.parent_id != s.parent_id and s.location and prior.location:
                            findings.append(Finding(
                                id=f"shadowing::{s.id}::{prior.id}",
                                rule_id="variable_shadowing",
                                message=f"Symbol '{s.name}' shadows definition from line {prior.location.start_line}",
                                severity=self.severity_default,
                                location=s.location,
                                symbol_id=s.id,
                                fix_hint=f"Rename '{s.name}' to avoid confusion with outer scope definition",
                                confidence=0.8,
                            ))
                    else:
                        scope_names[s.name] = s
        return findings
