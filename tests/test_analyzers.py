"""Tests for defect analyzers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.analysis.circular import CircularDependencyAnalyzer
from codeui.analysis.dead_code import DeadCodeAnalyzer
from codeui.analysis.duplicates import DuplicateCodeAnalyzer
from codeui.analysis.undefined import UndefinedSymbolAnalyzer
from codeui.analysis.unresolved_import import UnresolvedImportAnalyzer
from codeui.analysis.base import AnalysisContext
from codeui.core.graph import Graph
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility

class TestAnalyzers(unittest.TestCase):
    def test_dead_code_analyzer(self):
        g = Graph()
        s = Symbol(
            id="a.py::_unused_private",
            name="_unused_private",
            qualified_name="_unused_private",
            kind=SymbolKind.FUNCTION,
            language="python",
            location=Location("a.py", 1, 0, 2, 0),
            parent_id=None,
            signature="def _unused_private()",
            visibility=Visibility.PRIVATE,
            modifiers=(),
            content_hash="h",
        )
        g.add_symbol(s)
        analyzer = DeadCodeAnalyzer()
        findings = list(analyzer.run(g, AnalysisContext(Path("."))))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "dead_code")

    def test_circular_dependency(self):
        g = Graph()
        g.add_edge(Edge("a.py", "module::b", EdgeKind.IMPORTS, 1.0, 1.0, Location("a.py", 1, 0, 1, 0)))
        g.add_edge(Edge("b.py", "module::a", EdgeKind.IMPORTS, 1.0, 1.0, Location("b.py", 1, 0, 1, 0)))
        analyzer = CircularDependencyAnalyzer()
        findings = list(analyzer.run(g, AnalysisContext(Path("."))))
        self.assertGreaterEqual(len(findings), 1)

    def test_undefined_symbol_receiver_handling(self):
        g = Graph()
        loc = Location("a.py", 1, 0, 1, 10)
        g.add_symbol(Symbol("a.py::f", "f", "a.f", SymbolKind.FUNCTION, "python", loc, None, "def f()", Visibility.PUBLIC, (), "h1"))
        g.add_edge(Edge("a.py::f", "items.append", EdgeKind.CALLS, 1.0, 1.0, loc))
        analyzer = UndefinedSymbolAnalyzer()
        findings = list(analyzer.run(g, AnalysisContext(Path("."))))
        self.assertEqual(len(findings), 0)

    def test_shadowing_analyzer(self):
        from codeui.analysis.shadowing import ShadowingAnalyzer
        g = Graph()
        loc1 = Location("a.py", 1, 0, 1, 10)
        loc2 = Location("a.py", 5, 0, 5, 10)
        g.add_symbol(Symbol("a.py::outer_fn", "foo", "a.foo", SymbolKind.FUNCTION, "python", loc1, "a.py", "def foo()", Visibility.PUBLIC, (), "h1"))
        g.add_symbol(Symbol("a.py::inner_fn", "foo", "a.inner.foo", SymbolKind.FUNCTION, "python", loc2, "a.py::outer_fn", "def foo()", Visibility.PUBLIC, (), "h2"))
        analyzer = ShadowingAnalyzer()
        findings = list(analyzer.run(g, AnalysisContext(Path("."))))
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "variable_shadowing")

    def test_api_drift_analyzer(self):
        import json
        import tempfile
        from codeui.analysis.api_drift import ApiDriftAnalyzer
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            baseline = {
                "a.py::public_func": {
                    "name": "public_func",
                    "visibility": "public",
                    "signature": "def public_func(a: int) -> int",
                    "file_id": "a.py"
                }
            }
            (tmppath / "api_baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
            g = Graph()
            analyzer = ApiDriftAnalyzer()
            findings = list(analyzer.run(g, AnalysisContext(tmppath)))
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].rule_id, "api_drift")

if __name__ == "__main__":
    unittest.main()
