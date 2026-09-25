"""Tests for CLI commands."""
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.cli.main import main, scan_project

class TestCLI(unittest.TestCase):
    def test_cli_langs(self):
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            ret = main(["langs", "--json"])
            self.assertEqual(ret, 0)
            self.assertIn("python", buffer.getvalue())
        finally:
            sys.stdout = old_stdout

    def test_scan_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("def main():\n    print('Hello')\n", encoding="utf-8")
            (root / "src" / "utils.py").write_text("def helper():\n    pass\n", encoding="utf-8")
            graph1 = scan_project(root)
            self.assertGreaterEqual(len(graph1.get_all_files()), 2)
            self.assertTrue(graph1.has_symbol("src/app.py::main"))
            self.assertTrue((root / ".codeui" / "cache.db").exists())
            graph2 = scan_project(root)
            self.assertTrue(graph2.has_symbol("src/app.py::main"))

    def test_diff_array_format(self):
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "overrides.json"
            p.write_text(json.dumps([{"kind": "replace_file", "target_id": "a.py", "new_value": "x = 1"}]), encoding="utf-8")
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                ret = main(["diff", "--overrides", str(p), "--json"])
                self.assertEqual(ret, 0)
            finally:
                sys.stdout = old_stdout

    def test_cli_apply_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "script.py"
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                ret = main(["apply", "script.py", "--project", str(root), "--content", "print('applied')", "--disk"])
                self.assertEqual(ret, 0)
                self.assertTrue(target.exists())
                self.assertEqual(target.read_text(encoding="utf-8"), "print('applied')")
            finally:
                sys.stdout = old_stdout

if __name__ == "__main__":
    unittest.main()
