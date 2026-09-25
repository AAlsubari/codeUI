"""Runner executing all active defect analyzers against codeui Graph."""
from pathlib import Path
from typing import Dict, List, Sequence
from codeui.analysis.api_drift import ApiDriftAnalyzer
from codeui.analysis.base import AnalysisContext, Analyzer
from codeui.analysis.circular import CircularDependencyAnalyzer
from codeui.analysis.dead_code import DeadCodeAnalyzer
from codeui.analysis.duplicates import DuplicateCodeAnalyzer
from codeui.analysis.shadowing import ShadowingAnalyzer
from codeui.analysis.undefined import UndefinedSymbolAnalyzer
from codeui.analysis.unreachable import UnreachableCodeAnalyzer
from codeui.analysis.unresolved_import import UnresolvedImportAnalyzer
from codeui.core.graph import Graph
from codeui.core.ir import Finding

class AnalysisRunner:
    """Executes registered defect analyzers on a Graph.
    Example:
        >>> runner = AnalysisRunner()
        >>> g = Graph()
        >>> ctx = AnalysisContext(Path("."))
        >>> findings = runner.run_all(g, ctx)
        >>> isinstance(findings, list)
        True
    """
    def __init__(self, analyzers: Sequence[Analyzer] | None = None) -> None:
        if analyzers is None:
            self.analyzers: List[Analyzer] = [
                UndefinedSymbolAnalyzer(),
                DeadCodeAnalyzer(),
                UnresolvedImportAnalyzer(),
                CircularDependencyAnalyzer(),
                DuplicateCodeAnalyzer(),
                UnreachableCodeAnalyzer(),
                ShadowingAnalyzer(),
                ApiDriftAnalyzer(),
            ]
        else:
            self.analyzers = list(analyzers)

    def run_all(self, graph: Graph, ctx: AnalysisContext) -> List[Finding]:
        """Run all active analyzers and store findings on graph.
        Example:
            >>> runner = AnalysisRunner()
            >>> g = Graph()
            >>> ctx = AnalysisContext(Path("."))
            >>> findings = runner.run_all(g, ctx)
            >>> len(findings) == len(g.get_findings())
            True
        """
        all_findings: List[Finding] = []
        for analyzer in self.analyzers:
            findings = list(analyzer.run(graph, ctx))
            for f in findings:
                graph.add_finding(f)
                all_findings.append(f)
        return all_findings
