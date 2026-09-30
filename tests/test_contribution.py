"""Unit tests for ContributionManager and agent feedback tools."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.agent.contribution import ContributionManager
from codeui.agent.integrations import CodeUITools
from codeui.core.graph import Graph
from codeui.core.repo import get_library_repo_url

class TestContribution(unittest.TestCase):
    def test_get_library_repo_url(self):
        url = get_library_repo_url()
        self.assertEqual(url, "https://github.com/AAlsubari/codeUI")

    def test_clean_branch_name(self):
        mgr = ContributionManager()
        self.assertEqual(mgr.clean_branch_name("Fix AST Leak!"), "agent/fix-ast-leak")
        self.assertEqual(mgr.clean_branch_name("agent/already-branch"), "agent/already-branch")

    def test_apply_and_commit_changes_local(self):
        git_bin = shutil.which("git")
        if not git_bin:
            self.skipTest("git executable not found")

        with tempfile.TemporaryDirectory() as td:
            repo_path = Path(td)
            subprocess.run([git_bin, "init"], cwd=repo_path, capture_output=True, text=True)

            mgr = ContributionManager()
            applied = mgr.apply_changes(repo_path, {"test.py": "x = 100\n"})
            self.assertEqual(applied, ["test.py"])
            self.assertTrue((repo_path / "test.py").exists())

            msg = mgr.commit_changes(repo_path, "Initial agent commit")
            self.assertIn("Initial agent commit", msg)

    def test_codeui_tools_contribution_methods(self):
        g = Graph()
        tools = CodeUITools(g)
        self.assertEqual(tools.get_repository_url(), "https://github.com/AAlsubari/codeUI")

if __name__ == "__main__":
    unittest.main()
