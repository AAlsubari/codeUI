"""Tests for logic tracer."""
import sys
import unittest
from pathlib import Path

# sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.core.graph import Graph
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.tracer.tracer import Tracer

class TestTracer(unittest.TestCase):
    def test_tracer_forward(self):
        g = Graph()
        s1 = Symbol("a::f", "f", "f", SymbolKind.FUNCTION, "python", Location("a", 1, 0, 1, 0), None, "def f()", Visibility.PUBLIC, (), "h")
        s2 = Symbol("b::g", "g", "g", SymbolKind.FUNCTION, "python", Location("b", 1, 0, 1, 0), None, "def g()", Visibility.PUBLIC, (), "h")
        g.add_symbol(s1)
        g.add_symbol(s2)
        g.add_edge(Edge("b::g", "a::f", EdgeKind.CALLS, 1.0, 1.0, Location("b", 1, 0, 1, 0)))
        tracer = Tracer(g)
        callers = list(tracer.forward("a::f"))
        self.assertEqual(len(callers), 1)
        self.assertEqual(callers[0].id, "b::g")

    def test_user_entry_precedence(self):
        g = Graph()
        g.set_entry_points(["scripts/custom_etl.py"])
        s_custom = Symbol("scripts/custom_etl.py::run_pipeline", "run_pipeline", "run_pipeline", SymbolKind.FUNCTION, "python", Location("scripts/custom_etl.py", 1, 0, 1, 0), None, "def run_pipeline()", Visibility.PUBLIC, (), "h1")
        s_ignored = Symbol("other.py::helper", "helper", "helper", SymbolKind.FUNCTION, "python", Location("other.py", 1, 0, 1, 0), None, "def helper()", Visibility.PUBLIC, (), "h2")
        g.add_symbol(s_custom)
        g.add_symbol(s_ignored)
        tracer = Tracer(g)
        entries = [s.name for s in tracer.entry_points()]
        self.assertEqual(entries, ["run_pipeline"])

    def test_tracer_exact_root_entry_vs_nested(self):
        g = Graph()
        g.set_entry_points(["__init__.py"])
        s_root = Symbol("__init__.py::init_root", "init_root", "init_root", SymbolKind.FUNCTION, "python", Location("__init__.py", 1, 0, 1, 0), None, "def init_root()", Visibility.PUBLIC, (), "h1")
        s_nested = Symbol("agent/__init__.py::init_agent", "init_agent", "init_agent", SymbolKind.FUNCTION, "python", Location("agent/__init__.py", 1, 0, 1, 0), None, "def init_agent()", Visibility.PUBLIC, (), "h2")
        g.add_symbol(s_root)
        g.add_symbol(s_nested)
        tracer = Tracer(g)
        entries = [s.name for s in tracer.entry_points()]
        self.assertEqual(entries, ["init_root"])

if __name__ == "__main__":
    unittest.main()
