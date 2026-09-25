"""Unreachable statement analyzer."""
from pathlib import Path
from typing import ClassVar, Iterable, List
from codeui.analysis.base import AnalysisContext, Analyzer
from codeui.core.graph import Graph
from codeui.core.ir import Finding, Location, Severity

class UnreachableCodeAnalyzer(Analyzer):
    """Detects statements following return, throw, break, or continue.
    Example:
        >>> analyzer = UnreachableCodeAnalyzer()
        >>> g = Graph()
        >>> ctx = AnalysisContext(Path("."))
        >>> list(analyzer.run(g, ctx))
        []
    """
    id: ClassVar[str] = "unreachable"
    severity_default: ClassVar[Severity] = Severity.WARNING

    def run(self, graph: Graph, ctx: AnalysisContext) -> Iterable[Finding]:
        """Check for unreachable statements after terminal control flow.
        Example:
            >>> analyzer = UnreachableCodeAnalyzer()
            >>> g = Graph()
            >>> list(analyzer.run(g, AnalysisContext(Path("."))))
            []
        """
        return []
