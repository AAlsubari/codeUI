"""Tests for core Graph logic."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.core.graph import Graph
from codeui.core.ir import Edge, EdgeKind, LayerKind, Location, Symbol, SymbolKind, Visibility

class TestGraph(unittest.TestCase):
    def test_graph_add_and_query(self):
        g = Graph()
        s = Symbol(
            id="app.py::main",
            name="main",
            qualified_name="main",
            kind=SymbolKind.FUNCTION,
            language="python",
            location=Location("app.py", 1, 0, 2, 0),
            parent_id=None,
            signature="def main()",
            visibility=Visibility.PUBLIC,
            modifiers=(),
            content_hash="h",
        )
        g.add_symbol(s)
        self.assertTrue(g.has_symbol("app.py::main"))
        self.assertEqual(g.get_symbol("app.py::main").name, "main")
        self.assertEqual(g.get_file_classification("app.py").layer, LayerKind.ENTRY)

    def test_microservice_hierarchy_derivation(self):
        from codeui.core.graph import classify_file
        c1 = classify_file("services/billing/invoices/tax/calculator.py")
        self.assertEqual(c1.module, "billing")
        self.assertEqual(c1.feature, "billing/invoices/tax")

        c2 = classify_file("crates/engine/physics/collision.rs")
        self.assertEqual(c2.module, "engine")
        self.assertEqual(c2.feature, "engine/physics")

        c3 = classify_file("domain/auth/oauth/handler.py")
        self.assertEqual(c3.module, "domain")
        self.assertEqual(c3.feature, "domain/auth/oauth")

    def test_custom_layer_rules(self):
        from codeui.core.graph import classify_file
        custom_rules = {
            "backend": ["custom_pipeline/*", "etl/*"],
            "shared": ["core_types/*"]
        }
        c = classify_file("custom_pipeline/processor.py", layer_rules=custom_rules)
        self.assertEqual(str(c.layer), "backend")
        self.assertEqual(c.feature, "custom_pipeline")

    def test_entry_point_exact_matching(self):
        from codeui.core.graph import classify_file
        root_c = classify_file("__init__.py", entry_points=["__init__.py"])
        self.assertEqual(root_c.layer, LayerKind.ENTRY)

        nested_c = classify_file("agent/__init__.py", entry_points=["__init__.py"])
        self.assertNotEqual(nested_c.layer, LayerKind.ENTRY)
        self.assertEqual(nested_c.module, "agent")

        layer_rules = {"entry": ["codeui/__init__.py", "__init__.py"]}
        nested_rules_c = classify_file("agent/__init__.py", layer_rules=layer_rules)
        self.assertNotEqual(nested_rules_c.layer, LayerKind.ENTRY)

    def test_multihop_subgraph_cross_symbols(self):
        g = Graph()
        sA = Symbol("src/a.py::fnA", "fnA", "fnA", SymbolKind.FUNCTION, "python", Location("src/a.py", 1, 0, 5, 0), None, "def fnA()", Visibility.PUBLIC, (), "hA")
        sB = Symbol("src/b.py::fnB", "fnB", "fnB", SymbolKind.FUNCTION, "python", Location("src/b.py", 1, 0, 5, 0), None, "def fnB()", Visibility.PUBLIC, (), "hB")
        sC = Symbol("src/c.py::fnC", "fnC", "fnC", SymbolKind.FUNCTION, "python", Location("src/c.py", 1, 0, 5, 0), None, "def fnC()", Visibility.PUBLIC, (), "hC")
        sFileB = Symbol("src/b.py", "b.py", "b.py", SymbolKind.FILE, "python", Location("src/b.py", 1, 0, 5, 0), None, "", Visibility.PUBLIC, (), "hFB")
        
        g.add_symbol(sA)
        g.add_symbol(sB)
        g.add_symbol(sC)
        g.add_symbol(sFileB)
        
        g.add_edge(Edge("src/a.py::fnA", "src/b.py::fnB", EdgeKind.CALLS, 1.0, 1.0, None))
        g.add_edge(Edge("src/b.py::fnB", "src/c.py::fnC", EdgeKind.CALLS, 1.0, 1.0, None))
        g.add_edge(Edge("src/a.py::fnA", "src/b.py", EdgeKind.IMPORTS, 1.0, 1.0, None))
        
        sub = g.get_file_subgraph("src/a.py")
        self.assertEqual(sub["file_id"], "src/a.py")
        self.assertEqual(len(sub["symbols"]), 1)
        self.assertEqual(sub["symbols"][0]["name"], "fnA")
        
        related_ids = [s["id"] for s in sub["related_symbols"]]
        self.assertIn("src/b.py::fnB", related_ids)
        self.assertIn("src/c.py::fnC", related_ids)
        self.assertNotIn("src/b.py", related_ids)
        
        for s in sub["related_symbols"]:
            self.assertNotEqual(s["kind"], "file")
            self.assertTrue(s["is_external"])

    def test_get_files_info_hierarchy_and_symbol_count(self):
        g = Graph()
        sA = Symbol("src/core/a.py::fnA", "fnA", "fnA", SymbolKind.FUNCTION, "python", Location("src/core/a.py", 1, 0, 5, 0), None, "def fnA()", Visibility.PUBLIC, (), "hA")
        sFileEmpty = Symbol("src/empty.py", "empty.py", "empty.py", SymbolKind.FILE, "python", Location("src/empty.py", 1, 0, 1, 0), None, "", Visibility.PUBLIC, (), "hE")
        g.add_symbol(sA)
        g.add_symbol(sFileEmpty)
        
        info = g.get_files_info()
        self.assertIn("src/core/a.py", info)
        self.assertIn("src/empty.py", info)
        
        a_info = info["src/core/a.py"]
        self.assertEqual(a_info["folder"], "src/core")
        self.assertEqual(a_info["main_folder"], "src")
        self.assertEqual(a_info["subfolder"], "core")
        self.assertEqual(a_info["symbol_count"], 1)
        
        empty_info = info["src/empty.py"]
        self.assertEqual(empty_info["folder"], "src")
        self.assertEqual(empty_info["main_folder"], "src")
        self.assertEqual(empty_info["symbol_count"], 0)
        self.assertEqual(empty_info["total_symbols_count"], 1)

    def test_file_level_subgraph_with_file_edges(self):
        g = Graph()
        sInit = Symbol("src/pkg/__init__.py", "__init__.py", "__init__.py", SymbolKind.FILE, "python", Location("src/pkg/__init__.py", 1, 0, 5, 0), None, "", Visibility.PUBLIC, (), "hInit")
        sMod = Symbol("src/pkg/mod.py::Helper", "Helper", "Helper", SymbolKind.CLASS, "python", Location("src/pkg/mod.py", 1, 0, 10, 0), None, "class Helper", Visibility.PUBLIC, (), "hMod")
        g.add_symbol(sInit)
        g.add_symbol(sMod)
        g.add_edge(Edge("src/pkg/__init__.py", "module::external_lib", EdgeKind.IMPORTS, 1.0, 1.0, None))
        g.add_edge(Edge("src/pkg/__init__.py", "src/pkg/mod.py::Helper", EdgeKind.IMPORTS, 1.0, 1.0, None))

        sub = g.get_file_subgraph("src/pkg/__init__.py")
        self.assertEqual(sub["file_id"], "src/pkg/__init__.py")
        self.assertTrue(len(sub["symbols"]) >= 1)
        related_ids = [s["id"] for s in sub["related_symbols"]]
        self.assertNotIn("module::external_lib", related_ids)
        self.assertIn("src/pkg/mod.py::Helper", related_ids)
        self.assertTrue(len(sub["edges"]) >= 1)

if __name__ == "__main__":
    unittest.main()
