"""Tests for edge cases."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.core.graph import Graph
from codeui.core.ir import Finding, Location, Severity
from codeui.report.sarif_emitter import SARIFEmitter

class TestEdgeCases(unittest.TestCase):
    def test_sarif_emitter(self):
        g = Graph()
        g.add_finding(Finding("f1", "dead_code", "Unused func", Severity.WARNING, Location("a.py", 1, 0, 1, 0), "s1", "remove", 0.9))
        sarif_str = SARIFEmitter().emit(g)
        self.assertIn("dead_code", sarif_str)
        self.assertIn("https://raw.githubusercontent.com/oasis-tcs/sarif-spec", sarif_str)

if __name__ == "__main__":
    unittest.main()
