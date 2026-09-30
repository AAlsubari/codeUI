"""Cache layer for per-file analysis results based on content hashes."""
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict

class AnalysisCache:
    """SQLite-backed persistent cache for per-file symbol and edge extraction.
    Example:
        >>> cache = AnalysisCache(Path(".codeui/test_cache.db"))
        >>> cache.get("a.py", "hash123") is None
        True
        >>> cache.close()
    """
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self._init_db()

    def _init_db(self) -> None:
        """Create cache tables if they do not exist."""
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_cache (
                    file_path TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def get(self, file_path: str, content_hash: str) -> Dict[str, Any] | None:
        """Fetch cached symbols and edges for a file matching content hash.
        Example:
            >>> cache = AnalysisCache(Path(".codeui/test_cache.db"))
            >>> cache.get("file.py", "hash") is None
            True
            >>> cache.close()
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT content_hash, payload_json FROM file_cache WHERE file_path = ?",
            (file_path,),
        )
        row = cursor.fetchone()
        if row and row[0] == content_hash:
            return json.loads(row[1])
        return None

    def put(self, file_path: str, content_hash: str, payload: Dict[str, Any]) -> None:
        """Save analysis payload into cache.
        Example:
            >>> cache = AnalysisCache(Path(".codeui/test_cache.db"))
            >>> cache.put("file.py", "h1", {"symbols": []})
            >>> cache.get("file.py", "h1")["symbols"]
            []
            >>> cache.close()
        """
        payload_json = json.dumps(payload, sort_keys=True)
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO file_cache (file_path, content_hash, payload_json)
                VALUES (?, ?, ?)
                """,
                (file_path, content_hash, payload_json),
            )

    def invalidate(self, file_path: str) -> None:
        """Invalidate cached entry for file.
        Example:
            >>> cache = AnalysisCache(Path(".codeui/test_cache.db"))
            >>> cache.invalidate("file.py")
            >>> cache.close()
        """
        with self.conn:
            self.conn.execute("DELETE FROM file_cache WHERE file_path = ?", (file_path,))

    def put_symbols(self, file_path: str, content_hash: str, symbols: Any) -> None:
        """Store list of Symbol objects in cache."""
        self.put(file_path, content_hash, {"symbols": [s.to_dict() if hasattr(s, "to_dict") else s for s in symbols]})

    def get_symbols(self, file_path: str, content_hash: str) -> Any:
        """Retrieve list of Symbol objects from cache."""
        data = self.get(file_path, content_hash)
        if data is None or "symbols" not in data:
            return None
        from codeui.core.ir import Location, Symbol, SymbolKind, Visibility
        result = []
        for s in data["symbols"]:
            loc_data = s.get("location", {})
            loc = Location(
                file_id=loc_data.get("file_id", file_path),
                start_line=loc_data.get("start_line", 1),
                start_col=loc_data.get("start_col", 0),
                end_line=loc_data.get("end_line", 1),
                end_col=loc_data.get("end_col", 0),
            )
            sym = Symbol(
                id=s["id"],
                name=s["name"],
                qualified_name=s["qualified_name"],
                kind=SymbolKind(s["kind"]),
                language=s["language"],
                location=loc,
                parent_id=s.get("parent_id"),
                signature=s.get("signature"),
                visibility=Visibility(s.get("visibility", "public")),
                modifiers=tuple(s.get("modifiers", ())),
                content_hash=s.get("content_hash", ""),
            )
            result.append(sym)
        return result

    def clear(self) -> None:
        """Clear all entries from the cache database.
        Example:
            >>> cache = AnalysisCache(Path(".codeui/test_cache.db"))
            >>> cache.clear()
            >>> cache.close()
        """
        with self.conn:
            self.conn.execute("DELETE FROM file_cache")

    def prune_stale(self, existing_file_paths: Any) -> int:
        """Remove cached entries for files that no longer exist on disk.
        Example:
            >>> cache = AnalysisCache(Path(".codeui/test_cache.db"))
            >>> cache.prune_stale(["a.py"])
            0
            >>> cache.close()
        """
        valid_set = set(existing_file_paths)
        cursor = self.conn.cursor()
        cursor.execute("SELECT file_path FROM file_cache")
        cached_paths = [row[0] for row in cursor.fetchall()]
        stale_paths = [p for p in cached_paths if p not in valid_set]
        if stale_paths:
            with self.conn:
                self.conn.executemany(
                    "DELETE FROM file_cache WHERE file_path = ?",
                    [(p,) for p in stale_paths],
                )
        return len(stale_paths)

    def close(self) -> None:
        """Close SQLite database connection.
        Example:
            >>> cache = AnalysisCache(Path(".codeui/test_cache.db"))
            >>> cache.close()
        """
        self.conn.close()

Cache = AnalysisCache

def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of source code text.
    Example:
        >>> h = compute_content_hash("print('hello')")
        >>> len(h)
        64
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def remove_stale_cache(cache_path: Path) -> bool:
    """Dynamically remove stale cache file or directory.
    Example:
        >>> p = Path(".codeui/stale_test.db")
        >>> remove_stale_cache(p)
        False
    """
    path = Path(cache_path)
    if path.is_file():
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError:
            return False
    if path.is_dir():
        import shutil
        try:
            shutil.rmtree(path, ignore_errors=True)
            return True
        except OSError:
            return False
    return False
