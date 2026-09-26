"""Tests for OverrideStore."""
import sys
import unittest
from pathlib import Path

#sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.core.override import Override, OverrideKind, OverrideStore

class TestOverrides(unittest.TestCase):
    def test_override_store(self):
        store = OverrideStore()
        store.set_file_override("test.py", "x = 1", "x = 2", author="tester")
        self.assertEqual(store.get_file_content("test.py"), "x = 2")
        self.assertTrue(store.has_override("test.py"))
        diff = store.to_diff()
        self.assertIn("+x = 2", diff)
        store.revert("test.py")
        self.assertFalse(store.has_override("test.py"))

if __name__ == "__main__":
    unittest.main()
