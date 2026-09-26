"""Tests for core Graph logic."""
import sys
import unittest
from pathlib import Path

# sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

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

if __name__ == "__main__":
    unittest.main()
