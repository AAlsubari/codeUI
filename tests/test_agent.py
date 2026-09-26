"""Tests for agent context builder and edit tools."""
import sys
import unittest
from pathlib import Path

#sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.agent.context import ContextBuilder, TaskSpec
from codeui.agent.edit_tools import EditTools
from codeui.agent.integrations import CodeUITools
from codeui.agent.mcp_server import MCPServer
from codeui.core.graph import Graph
from codeui.core.ir import Location, Symbol, SymbolKind, Visibility
from codeui.core.override import OverrideStore

class TestAgent(unittest.TestCase):
    def setUp(self):
        self.graph = Graph()
        s1 = Symbol(
            id="app.py::main",
            name="main",
            qualified_name="app.main",
            kind=SymbolKind.FUNCTION,
            language="python",
            location=Location("app.py", 1, 0, 2, 0),
            parent_id=None,
            signature="def main()",
            visibility=Visibility.PUBLIC,
            modifiers=(),
            content_hash="h1",
        )
        s2 = Symbol(
            id="utils.py::helper",
            name="helper",
            qualified_name="utils.helper",
            kind=SymbolKind.FUNCTION,
            language="python",
            location=Location("utils.py", 1, 0, 2, 0),
            parent_id=None,
            signature="def helper()",
            visibility=Visibility.PUBLIC,
            modifiers=(),
            content_hash="h2",
        )
        self.graph.add_symbol(s1)
        self.graph.add_symbol(s2)
        self.store = OverrideStore()

    def test_context_builder(self):
        builder = ContextBuilder(self.graph)
        bundle = builder.for_symbol("app.py::main", depth=1)
        self.assertEqual(bundle.manifest["status"], "success")
        self.assertIn("app.py::main", bundle.symbol_bodies)

    def test_context_builder_task(self):
        builder = ContextBuilder(self.graph)
        spec = TaskSpec("Refactor main", target_symbols=["app.py::main"])
        bundle = builder.for_task(spec)
        self.assertEqual(bundle.manifest["query"], "Refactor main")

    def test_edit_tools(self):
        tools = EditTools(self.graph, self.store, direct_disk=False)
        prop = tools.replace_file("app.py", "x = 42")
        tools.apply(prop)
        self.assertEqual(self.store.get_file_content("app.py"), "x = 42")
        self.assertIn("--- a/app.py", tools.diff())

    def test_direct_disk_editing(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            tools = EditTools(self.graph, self.store, project_root=td, direct_disk=True)
            prop = tools.replace_file("module.py", "y = 100")
            tools.apply(prop)
            saved_file = Path(td) / "module.py"
            self.assertTrue(saved_file.exists())
            self.assertEqual(saved_file.read_text(encoding="utf-8"), "y = 100")

    def test_codeui_tools_direct_disk(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            tools = CodeUITools(self.graph, project_root=td, direct_disk=True)
            res = tools.write_file_direct("direct.py", "z = 999")
            self.assertEqual(res["status"], "saved_to_disk")
            self.assertTrue((Path(td) / "direct.py").exists())
            self.assertEqual((Path(td) / "direct.py").read_text(encoding="utf-8"), "z = 999")

            prop = tools.propose_replace_file("direct2.py", "w = 555")
            apply_res = tools.apply_proposal(prop, direct_disk=True)
            self.assertEqual(apply_res["status"], "written_to_disk")
            self.assertEqual((Path(td) / "direct2.py").read_text(encoding="utf-8"), "w = 555")

    def test_mcp_server(self):
        server = MCPServer(self.graph)
        res = server.handle_request({"method": "tools/list", "id": 1})
        self.assertIn("result", res)
        self.assertGreaterEqual(len(res["result"]["tools"]), 7)
        tool_names = [t["name"] for t in res["result"]["tools"]]
        self.assertIn("propose_replace_file", tool_names)
        self.assertIn("write_file_to_disk", tool_names)
        self.assertIn("get_diff", tool_names)

    def test_edit_tools_missing_symbol(self):
        from codeui.errors import SymbolNotFoundError
        tools = EditTools(self.graph, self.store)
        with self.assertRaises(SymbolNotFoundError):
            tools.rename_symbol("nonexistent", "new_name")

if __name__ == "__main__":
    unittest.main()
