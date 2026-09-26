"""Tests for import path resolution."""
import sys
import tempfile
import unittest
from pathlib import Path

#sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.core.resolver import ResolveContext

class TestResolver(unittest.TestCase):
    def test_resolve_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text("", encoding="utf-8")
            (root / "src" / "b.py").write_text("", encoding="utf-8")
            ctx = ResolveContext(root)
            resolved = ctx.resolve_path("src/a.py", ".b", "python")
            self.assertIn("src/b.py", resolved)

    def test_root_confinement_external_import_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            project_dir = workspace / "my_project"
            project_dir.mkdir()
            (project_dir / "app.py").write_text("", encoding="utf-8")
            
            outside_dir = workspace / "external_lib"
            outside_dir.mkdir()
            (outside_dir / "secret.py").write_text("", encoding="utf-8")

            ctx = ResolveContext(project_dir)
            resolved_outside = ctx.resolve_path("app.py", "../external_lib/secret", "python")
            self.assertEqual(resolved_outside, [])
            
            resolved_mod = ctx.resolve_path("app.py", "external_lib.secret", "python")
            self.assertEqual(resolved_mod, [])

if __name__ == "__main__":
    unittest.main()
