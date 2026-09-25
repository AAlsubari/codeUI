"""Tests for Git repo clone detection."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.core.repo import is_git_url

class TestRepo(unittest.TestCase):
    def test_git_url_detection(self):
        self.assertTrue(is_git_url("https://github.com/org/repo.git"))
        self.assertTrue(is_git_url("git@github.com:org/repo.git"))
        self.assertFalse(is_git_url("/local/path/to/project"))

if __name__ == "__main__":
    unittest.main()
