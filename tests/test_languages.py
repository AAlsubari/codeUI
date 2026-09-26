"""Tests for language analyzers."""
import sys
import unittest
from pathlib import Path

# sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.lang.python import PythonLanguageAnalyzer
from codeui.lang.ts import TSLanguageAnalyzer
from codeui.lang.go import GoLanguageAnalyzer
from codeui.lang.rust import RustLanguageAnalyzer

class TestLanguages(unittest.TestCase):
    def test_python_analyzer(self):
        p = PythonLanguageAnalyzer()
        res = p.parse(Path("test.py"), "def add(a, b): return a + b")
        syms = list(p.extract_symbols(res))
        self.assertTrue(any(s.name == "add" for s in syms))

    def test_ts_analyzer(self):
        ts = TSLanguageAnalyzer()
        res = ts.parse(Path("test.ts"), "export class User { id: number; }")
        syms = list(ts.extract_symbols(res))
        self.assertTrue(any(s.name == "User" for s in syms))

    def test_go_analyzer(self):
        go = GoLanguageAnalyzer()
        res = go.parse(Path("main.go"), "package main\\nfunc Main() {}")
        syms = list(go.extract_symbols(res))
        self.assertTrue(any(s.name == "Main" for s in syms))

    def test_rust_analyzer(self):
        rs = RustLanguageAnalyzer()
        res = rs.parse(Path("lib.rs"), "pub fn compute() {}")
        syms = list(rs.extract_symbols(res))
        self.assertTrue(any(s.name == "compute" for s in syms))

if __name__ == "__main__":
    unittest.main()
