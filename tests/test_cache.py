"""Tests for SQLite cache."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

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

    def test_cache_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cache.db"
            cache = Cache(db_path)
            cache.put("a.py", "h1", {"data": 123})
            self.assertIsNotNone(cache.get("a.py", "h1"))
            cache.clear()
            self.assertIsNone(cache.get("a.py", "h1"))
            cache.close()

    def test_cache_prune_stale(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cache.db"
            cache = Cache(db_path)
            cache.put("keep.py", "h1", {"data": 1})
            cache.put("stale.py", "h2", {"data": 2})
            pruned_count = cache.prune_stale(["keep.py"])
            self.assertEqual(pruned_count, 1)
            self.assertIsNotNone(cache.get("keep.py", "h1"))
            self.assertIsNone(cache.get("stale.py", "h2"))
            cache.close()

    def test_remove_stale_cache_util(self):
        from codeui.core.cache import remove_stale_cache
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "stale.db"
            target_file.write_text("dummy", encoding="utf-8")
            self.assertTrue(target_file.exists())
            removed = remove_stale_cache(target_file)
            self.assertTrue(removed)
            self.assertFalse(target_file.exists())

            target_dir = Path(tmpdir) / "stale_dir"
            target_dir.mkdir()
            (target_dir / "child.txt").write_text("data", encoding="utf-8")
            removed_dir = remove_stale_cache(target_dir)
            self.assertTrue(removed_dir)
            self.assertFalse(target_dir.exists())

if __name__ == "__main__":
    unittest.main()
