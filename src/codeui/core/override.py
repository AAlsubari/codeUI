"""In-memory OverrideStore for non-destructive code editing."""
import difflib
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from codeui.core.ir import StrEnum
from codeui.errors import OverrideConflictError

class OverrideKind(StrEnum):
    """Kind of override modification."""
    RENAME_SYMBOL = "rename_symbol"
    RETYPE_SYMBOL = "retype_symbol"
    REPLACE_SYMBOL_BODY = "replace_symbol_body"
    REPLACE_FILE = "replace_file"
    TOGGLE_EDGE = "toggle_edge"
    TRIAGE_FINDING = "triage_finding"

@dataclass
class Override:
    """Represents an active override on a target symbol, file, or edge.
    Example:
        >>> o = Override("sym_1", OverrideKind.RENAME_SYMBOL, "hash123", "new_name", "user", "2026-01-01T00:00:00Z")
        >>> o.target_id
        'sym_1'
    """
    target_id: str
    kind: OverrideKind
    original_hash: str
    new_value: Any
    author: str
    created_at: str
    note: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert override to serializable dict.
        Example:
            >>> o = Override("sym_1", OverrideKind.RENAME_SYMBOL, "hash123", "new_name", "user", "2026-01-01T00:00:00Z")
            >>> o.to_dict()["kind"]
            'rename_symbol'
        """
        d = asdict(self)
        d["kind"] = str(self.kind)
        return d

@dataclass(frozen=True)
class Conflict:
    """Override conflict descriptor.
    Example:
        >>> c = Conflict("src/main.py", "hash1", "hash2", "File on disk changed")
        >>> c.file_path
        'src/main.py'
    """
    file_path: str
    expected_hash: str
    actual_hash: str
    reason: str

class OverrideStore:
    """Manages active overrides without writing to disk.
    Example:
        >>> store = OverrideStore()
        >>> o = Override("file.py", OverrideKind.REPLACE_FILE, "h1", "print('hello')", "agent", "2026-01-01")
        >>> store.set(o)
        >>> store.get("file.py").new_value
        "print('hello')"
    """
    def __init__(self) -> None:
        self._overrides: Dict[str, Override] = {}
        self._file_contents: Dict[str, str] = {}
        self._original_file_contents: Dict[str, str] = {}

    def get(self, target_id: str) -> Override | None:
        """Retrieve active override for target ID.
        Example:
            >>> store = OverrideStore()
            >>> store.get("nonexistent") is None
            True
        """
        return self._overrides.get(target_id)

    def has_override(self, target_id: str) -> bool:
        """Check if target has an active override.
        Example:
            >>> store = OverrideStore()
            >>> store.has_override("test.py")
            False
        """
        return target_id in self._overrides

    def set(self, override: Override) -> None:
        """Set or update an override.
        Example:
            >>> store = OverrideStore()
            >>> o = Override("t1", OverrideKind.RENAME_SYMBOL, "h1", "new", "user", "2026")
            >>> store.set(o)
            >>> store.get("t1").new_value
            'new'
        """
        self._overrides[override.target_id] = override

    def set_file_override(self, file_path: str, original_content: str, new_content: str, author: str = "user", note: str | None = None) -> None:
        """Register full file replacement override.
        Example:
            >>> store = OverrideStore()
            >>> store.set_file_override("a.py", "x = 1", "x = 2")
            >>> store.get_file_content("a.py")
            'x = 2'
        """
        now = datetime.now(timezone.utc).isoformat()
        self._original_file_contents[file_path] = original_content
        self._file_contents[file_path] = new_content
        override = Override(
            target_id=file_path,
            kind=OverrideKind.REPLACE_FILE,
            original_hash=hashlib.sha256(original_content.encode("utf-8")).hexdigest(),
            new_value=new_content,
            author=author,
            created_at=now,
            note=note,
        )
        self._overrides[file_path] = override

    def get_file_content(self, file_path: str) -> str | None:
        """Return overridden file content if present.
        Example:
            >>> store = OverrideStore()
            >>> store.set_file_override("a.py", "old", "new")
            >>> store.get_file_content("a.py")
            'new'
        """
        return self._file_contents.get(file_path)

    def revert(self, target_id: str) -> None:
        """Revert override for specific target ID or file path across all key variations.
        Example:
            >>> store = OverrideStore()
            >>> store.set_file_override("a/b.py", "old", "new")
            >>> store.revert("b.py")
            >>> store.get("a/b.py") is None
            True
        """
        if not target_id:
            return
        clean_target = target_id.split("::")[0].replace("module::", "").replace("\\", "/").strip().lstrip("./")
        keys_to_remove = set()
        for k in list(self._overrides.keys()) + list(self._file_contents.keys()):
            k_clean = k.split("::")[0].replace("module::", "").replace("\\", "/").strip().lstrip("./")
            if k == target_id or k_clean == clean_target or k_clean.endswith("/" + clean_target) or clean_target.endswith("/" + k_clean):
                keys_to_remove.add(k)
        for k in keys_to_remove:
            self._overrides.pop(k, None)
            self._file_contents.pop(k, None)
            self._original_file_contents.pop(k, None)

    def revert_all(self) -> None:
        """Revert all overrides in the store.
        Example:
            >>> store = OverrideStore()
            >>> store.set_file_override("a.py", "old", "new")
            >>> store.revert_all()
            >>> len(list(store.list()))
            0
        """
        self._overrides.clear()
        self._file_contents.clear()

    def list(self) -> Iterable[Override]:
        """List all current overrides in deterministic order.
        Example:
            >>> store = OverrideStore()
            >>> list(store.list())
            []
        """
        return sorted(self._overrides.values(), key=lambda o: o.target_id)

    def to_patch_files(self) -> Dict[str, str]:
        """Export map of path to modified file content.
        Example:
            >>> store = OverrideStore()
            >>> store.set_file_override("a.py", "old", "new")
            >>> store.to_patch_files()["a.py"]
            'new'
        """
        return dict(self._file_contents)

    def to_diff(self) -> str:
        """Generate unified diff string across all overridden files.
        Example:
            >>> store = OverrideStore()
            >>> store.set_file_override("a.py", "old", "new")
            >>> '--- a/a.py' in store.to_diff()
            True
        """
        diff_chunks: List[str] = []
        for file_path in sorted(self._file_contents.keys()):
            orig = self._original_file_contents.get(file_path, "").splitlines(keepends=True)
            mod = self._file_contents[file_path].splitlines(keepends=True)
            lines = list(difflib.unified_diff(
                orig,
                mod,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            ))
            if lines:
                diff_chunks.extend(lines)
        return "".join(diff_chunks)

    def check_conflicts(self, disk_state: Dict[str, str]) -> List[Conflict]:
        """Check for conflicts between overrides and current disk files.
        Example:
            >>> store = OverrideStore()
            >>> store.set_file_override("a.py", "v1", "v2")
            >>> conflicts = store.check_conflicts({"a.py": "v1_changed"})
            >>> len(conflicts)
            1
        """
        conflicts: List[Conflict] = []
        for file_path, override in self._overrides.items():
            if override.kind == OverrideKind.REPLACE_FILE and file_path in disk_state:
                current_disk_content = disk_state[file_path]
                expected_original = self._original_file_contents.get(file_path, "")
                if current_disk_content != expected_original:
                    conflicts.append(Conflict(
                        file_path=file_path,
                        expected_hash=override.original_hash,
                        actual_hash=hashlib.sha256(current_disk_content.encode("utf-8")).hexdigest(),
                        reason="File content on disk changed since override creation",
                    ))
        return conflicts
