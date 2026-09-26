"""Tests for HTTP server endpoints."""
import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

# sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.core.graph import Graph
from codeui.core.ir import Location, Symbol, SymbolKind, Visibility
from codeui.core.override import OverrideStore
from codeui.server.server import create_server

class TestServer(unittest.TestCase):
    def test_server_health(self):
        graph = Graph()
        s = Symbol("app.py::main", "main", "main", SymbolKind.FUNCTION, "python", Location("app.py", 1, 0, 1, 0), None, "def main()", Visibility.PUBLIC, (), "h")
        graph.add_symbol(s)
        store = OverrideStore()
        server = create_server(graph, store, Path("."), port=0)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{port}/health"
            req = urllib.request.urlopen(url)
            self.assertEqual(req.status, 200)
            data = json.loads(req.read().decode())
            self.assertEqual(data["status"], "ok")
        finally:
            server.shutdown()
            server.server_close()

    def test_subgraph_cross_usage(self):
        graph = Graph()
        s1 = Symbol("app.py::main", "main", "main", SymbolKind.FUNCTION, "python", Location("app.py", 1, 0, 5, 0), None, "def main()", Visibility.PUBLIC, (), "h1")
        s2 = Symbol("utils.py::helper", "helper", "helper", SymbolKind.FUNCTION, "python", Location("utils.py", 1, 0, 3, 0), None, "def helper()", Visibility.PUBLIC, (), "h2")
        from codeui.core.ir import Edge, EdgeKind
        graph.add_symbol(s1)
        graph.add_symbol(s2)
        graph.add_edge(Edge("app.py::main", "utils.py::helper", EdgeKind.CALLS, 1.0, 1.0, None))
        store = OverrideStore()
        server = create_server(graph, store, Path("."), port=0)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{port}/api/v1/subgraph?file=app.py"
            req = urllib.request.urlopen(url)
            self.assertEqual(req.status, 200)
            data = json.loads(req.read().decode())
            self.assertEqual(data["file_id"], "app.py")
            self.assertEqual(len(data["symbols"]), 1)
            self.assertEqual(data["symbols"][0]["name"], "main")
            self.assertEqual(len(data["related_symbols"]), 1)
            self.assertEqual(data["related_symbols"][0]["name"], "helper")
            self.assertTrue(data["related_symbols"][0]["is_external"])
            self.assertEqual(len(data["edges"]), 1)
        finally:
            server.shutdown()
            server.server_close()

    def test_server_edit_direct_disk(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            graph = Graph()
            store = OverrideStore()
            server = create_server(graph, store, Path(td), port=0)
            port = server.server_port
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{port}/api/v1/edit"
                req_data = json.dumps({
                    "kind": "replace_file",
                    "target_id": "hello.py",
                    "new_value": "print('world')",
                    "direct_disk": True,
                }).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=req_data,
                    headers={"Content-Type": "application/json", "X-CSRF-Token": "codeui-local-csrf-token"}
                )
                with urllib.request.urlopen(req) as resp:
                    self.assertEqual(resp.status, 200)
                    resp_json = json.loads(resp.read().decode())
                    self.assertEqual(resp_json["status"], "ok")
                    self.assertTrue(resp_json["direct_disk"])
                
                target_disk_file = Path(td) / "hello.py"
                self.assertTrue(target_disk_file.exists())
                self.assertEqual(target_disk_file.read_text(encoding="utf-8"), "print('world')")
            finally:
                server.shutdown()
                server.server_close()

    def test_rescan_preserves_entry_points(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "main_entry.py").write_text("def run(): pass", encoding="utf-8")
            (p / "helper.py").write_text("def help(): pass", encoding="utf-8")

            def mock_scan(root_path, entry_points=None, layer_rules=None):
                g = Graph()
                s1 = Symbol("main_entry.py::run", "run", "main_entry.run", SymbolKind.FUNCTION, "python", Location("main_entry.py", 1, 0, 1, 0), None, "def run():", Visibility.PUBLIC, (), "h1")
                s2 = Symbol("helper.py::help", "help", "helper.help", SymbolKind.FUNCTION, "python", Location("helper.py", 1, 0, 1, 0), None, "def help():", Visibility.PUBLIC, (), "h2")
                g.add_symbol(s1)
                g.add_symbol(s2)
                if entry_points:
                    g.set_entry_points(entry_points)
                return g

            g_initial = mock_scan(p, entry_points=["main_entry.py"])
            self.assertEqual(g_initial.get_file_classification("main_entry.py").layer.value, "entry")
            store = OverrideStore()
            server = create_server(g_initial, store, p, port=0, rescan_fn=mock_scan, entry_points=["main_entry.py"])
            port = server.server_port
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                # Trigger a direct disk edit which invokes execute_rescan
                url = f"http://127.0.0.1:{port}/api/v1/edit"
                req_data = json.dumps({
                    "kind": "replace_file",
                    "target_id": "helper.py",
                    "new_value": "def help_modified(): pass",
                    "direct_disk": True,
                }).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=req_data,
                    headers={"Content-Type": "application/json", "X-CSRF-Token": "codeui-local-csrf-token"}
                )
                with urllib.request.urlopen(req) as resp:
                    self.assertEqual(resp.status, 200)

                # Fetch updated graph: main_entry.py must STILL be classified as 'entry'
                graph_url = f"http://127.0.0.1:{port}/api/v1/graph"
                with urllib.request.urlopen(graph_url) as g_resp:
                    self.assertEqual(g_resp.status, 200)
                    g_data = json.loads(g_resp.read().decode())
                    files_info = g_data.get("files_info", {})
                    self.assertIn("main_entry.py", files_info)
                    self.assertEqual(files_info["main_entry.py"]["layer"], "entry")
            finally:
                server.shutdown()
                server.server_close()

if __name__ == "__main__":
    unittest.main()
