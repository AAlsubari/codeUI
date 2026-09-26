"""Tests for SQLite cache."""
import sys
import tempfile
import unittest
from pathlib import Path

#sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.core.cache import Cache
from codeui.core.ir import Location, Symbol, SymbolKind, Visibility

class TestCache(unittest.TestCase):
    def test_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cache.db"
            cache = Cache(db_path)
            sym = Symbol(
                id="s1",
                name="f",
                qualified_name="mod.f",
                kind=SymbolKind.FUNCTION,
                language="python",
                location=Location("a.py", 1, 0, 2, 0),
                parent_id=None,
                signature="def f()",
                visibility=Visibility.PUBLIC,
                modifiers=(),
                content_hash="h1",
            )
            cache.put_symbols("a.py", "h1", [sym])
            retrieved = cache.get_symbols("a.py", "h1")
            self.assertEqual(len(retrieved), 1)
            self.assertEqual(retrieved[0].id, "s1")
            self.assertIsNone(cache.get_symbols("a.py", "different_hash"))
            cache.close()

if __name__ == "__main__":
    unittest.main()
