"""Edit tools allowing agents to propose and apply non-destructive overrides."""
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from codeui.core.graph import Graph
from codeui.core.ir import SymbolKind
from codeui.core.override import Conflict, Override, OverrideKind, OverrideStore
from codeui.errors import SymbolNotFoundError, FileNotFoundInGraphError

@dataclass
class EditProposal:
    """Dry-run proposal report for edit tools.
    Example:
        >>> p = EditProposal("s1", "rename_symbol", ["s1"], ["a.py"], "diff preview", [])
        >>> p.target_id
        's1'
    """
    target_id: str
    kind: str
    affected_symbols: List[str]
    affected_files: List[str]
    diff_preview: str
    conflicts: List[Conflict]
    new_value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert EditProposal to dictionary.
        Example:
            >>> p = EditProposal("s1", "rename", [], [], "", [])
            >>> p.to_dict()["target_id"]
            's1'
        """
        return asdict(self)

class EditTools:
    """Provides agent interface to dry-run, apply code overrides, and edit project files directly on disk.
    Example:
        >>> g = Graph()
        >>> store = OverrideStore()
        >>> tools = EditTools(g, store)
        >>> tools.diff()
        ''
    """
    def __init__(
        self,
        graph: Graph,
        override_store: Optional[OverrideStore] = None,
        project_root: Optional[Union[str, Path]] = None,
        direct_disk: bool = True,
    ) -> None:
        self.graph = graph
        self.override_store = override_store if override_store is not None else OverrideStore()
        self.project_root = Path(project_root).resolve() if project_root else None
        self.direct_disk = direct_disk

    def rename_symbol(self, symbol_id: str, new_name: str) -> EditProposal:
        """Propose renaming a symbol and updating references.
        Example:
            >>> from codeui.core.ir import Symbol, Location, Visibility
            >>> g = Graph()
            >>> g.add_symbol(Symbol("s1", "f", "a.f", SymbolKind.FUNCTION, "python", Location("a.py", 1, 0, 2, 0), None, None, Visibility.PUBLIC, (), "h"))
            >>> store = OverrideStore()
            >>> tools = EditTools(g, store)
            >>> prop = tools.rename_symbol("s1", "new_name")
            >>> prop.target_id
            's1'
        """
        if not self.graph.has_symbol(symbol_id):
            raise SymbolNotFoundError(symbol_id)
        sym = self.graph.get_symbol(symbol_id)
        affected_files = [sym.location.file_id]
        incoming = self.graph.get_incoming_edges(symbol_id)
        affected_symbols = [symbol_id] + [e.source_id for e in incoming]
        diff_preview = f"--- a/{sym.location.file_id}\n+++ b/{sym.location.file_id}\n- {sym.name}\n+ {new_name}\n"
        return EditProposal(
            target_id=symbol_id,
            kind="rename_symbol",
            affected_symbols=affected_symbols,
            affected_files=affected_files,
            diff_preview=diff_preview,
            conflicts=[],
            new_value=new_name,
        )

    def retype_symbol(self, symbol_id: str, new_kind: SymbolKind) -> EditProposal:
        """Propose retyping a symbol's SymbolKind.
        Example:
            >>> from codeui.core.ir import Symbol, Location, Visibility
            >>> g = Graph()
            >>> g.add_symbol(Symbol("s1", "f", "a.f", SymbolKind.FUNCTION, "python", Location("a.py", 1, 0, 2, 0), None, None, Visibility.PUBLIC, (), "h"))
            >>> store = OverrideStore()
            >>> tools = EditTools(g, store)
            >>> prop = tools.retype_symbol("s1", SymbolKind.METHOD)
            >>> prop.kind
            'retype_symbol'
        """
        if not self.graph.has_symbol(symbol_id):
            raise SymbolNotFoundError(symbol_id)
        sym = self.graph.get_symbol(symbol_id)
        return EditProposal(
            target_id=symbol_id,
            kind="retype_symbol",
            affected_symbols=[symbol_id],
            affected_files=[sym.location.file_id],
            diff_preview=f"Change kind of {sym.name} from {sym.kind} to {new_kind}",
            conflicts=[],
            new_value=new_kind,
        )

    def replace_symbol_body(self, symbol_id: str, new_body: str) -> EditProposal:
        """Propose replacing the implementation body of a single symbol.
        Example:
            >>> from codeui.core.ir import Symbol, Location, Visibility
            >>> g = Graph()
            >>> g.add_symbol(Symbol("s1", "f", "a.f", SymbolKind.FUNCTION, "python", Location("a.py", 1, 0, 2, 0), None, None, Visibility.PUBLIC, (), "h"))
            >>> store = OverrideStore()
            >>> tools = EditTools(g, store)
            >>> prop = tools.replace_symbol_body("s1", "def foo(): pass")
            >>> prop.target_id
            's1'
        """
        if not self.graph.has_symbol(symbol_id):
            raise SymbolNotFoundError(symbol_id)
        sym = self.graph.get_symbol(symbol_id)
        return EditProposal(
            target_id=symbol_id,
            kind="replace_symbol_body",
            affected_symbols=[symbol_id],
            affected_files=[sym.location.file_id],
            diff_preview=f"Replace body of {sym.name} with:\n{new_body}",
            conflicts=[],
            new_value=new_body,
        )

    def replace_file(self, file_id: str, new_content: str, original_content: str = "") -> EditProposal:
        """Propose replacing entire file content without mutating disk.
        Example:
            >>> g = Graph()
            >>> store = OverrideStore()
            >>> tools = EditTools(g, store)
            >>> prop = tools.replace_file("app.py", "x = 1", "x = 0")
            >>> prop.affected_files
            ['app.py']
        """
        diff = f"--- a/{file_id}\n+++ b/{file_id}\n{new_content}"
        return EditProposal(
            target_id=file_id,
            kind="replace_file",
            affected_symbols=[],
            affected_files=[file_id],
            diff_preview=diff,
            conflicts=[],
            new_value=new_content,
        )

    def write_file_to_disk(self, file_path: str, new_content: str) -> Path:
        """Write content directly to project file on disk.
        Example:
            >>> import tempfile
            >>> with tempfile.TemporaryDirectory() as td:
            ...     tools = EditTools(Graph(), project_root=td)
            ...     p = tools.write_file_to_disk("sub/app.py", "x = 1")
            ...     p.exists()
            True
        """
        root = (self.project_root if self.project_root is not None else Path(".")).resolve()
        clean_rel = file_path.split("::")[0].replace("module::", "").replace("\\", "/").lstrip("/")
        
        target_path: Optional[Path] = None
        cand_direct = (root / clean_rel).resolve()
        if cand_direct.exists() and cand_direct.is_file():
            target_path = cand_direct
        elif root.name and clean_rel.startswith(root.name + "/"):
            sub_cand = (root / clean_rel[len(root.name):].lstrip("/")).resolve()
            if sub_cand.exists() and sub_cand.is_file():
                target_path = sub_cand

        if target_path is None and self.graph:
            for known_file in self.graph.get_all_files():
                k_clean = known_file.replace("\\", "/").lstrip("./")
                if k_clean == clean_rel or k_clean.endswith("/" + clean_rel) or clean_rel.endswith("/" + k_clean):
                    cand_k = (root / k_clean).resolve()
                    if cand_k.exists() and cand_k.is_file():
                        target_path = cand_k
                        break

        if target_path is None:
            target_path = cand_direct

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(new_content, encoding="utf-8")
        if self.override_store:
            self.override_store.revert(clean_rel)
            try:
                rel = str(target_path.relative_to(root)).replace("\\", "/")
                self.override_store.revert(rel)
            except Exception:
                pass
        return target_path

    def apply_to_disk(self, proposal: EditProposal, author: str = "agent") -> Path:
        """Apply an EditProposal directly to project files on disk.
        Example:
            >>> import tempfile
            >>> with tempfile.TemporaryDirectory() as td:
            ...     tools = EditTools(Graph(), project_root=td)
            ...     prop = tools.replace_file("test.py", "val = 10")
            ...     path = tools.apply_to_disk(prop)
            ...     path.read_text()
            'val = 10'
        """
        content = proposal.new_value if proposal.new_value is not None else (
            proposal.diff_preview.split("\n", 2)[-1] if "\n" in proposal.diff_preview else proposal.diff_preview
        )
        return self.write_file_to_disk(proposal.target_id, content)

    def apply(self, proposal: EditProposal, author: str = "agent", write_to_disk: Optional[bool] = None) -> None:
        """Apply an EditProposal into OverrideStore or directly to project file on disk.
        Example:
            >>> g = Graph()
            >>> store = OverrideStore()
            >>> tools = EditTools(g, store, direct_disk=False)
            >>> prop = tools.replace_file("app.py", "x = 1")
            >>> tools.apply(prop)
            >>> store.get("app.py") is not None
            True
        """
        should_write_disk = write_to_disk if write_to_disk is not None else (self.direct_disk and self.project_root is not None)
        if should_write_disk and proposal.kind == "replace_file":
            content = proposal.new_value if proposal.new_value is not None else (
                proposal.diff_preview.split("\n", 2)[-1] if "\n" in proposal.diff_preview else proposal.diff_preview
            )
            self.write_file_to_disk(proposal.target_id, content)
            return

        now = datetime.now(timezone.utc).isoformat()
        if proposal.kind == "replace_file":
            content = proposal.new_value if proposal.new_value is not None else (
                proposal.diff_preview.split("\n", 2)[-1] if "\n" in proposal.diff_preview else proposal.diff_preview
            )
            self.override_store.set_file_override(
                file_path=proposal.target_id,
                original_content="",
                new_content=content,
                author=author,
            )
        else:
            val = proposal.new_value if proposal.new_value is not None else proposal.diff_preview
            override = Override(
                target_id=proposal.target_id,
                kind=OverrideKind(proposal.kind),
                original_hash="",
                new_value=val,
                author=author,
                created_at=now,
            )
            self.override_store.set(override)

    def revert(self, target_id: str) -> None:
        """Revert override for target ID.
        Example:
            >>> g = Graph()
            >>> store = OverrideStore()
            >>> tools = EditTools(g, store)
            >>> tools.revert("app.py")
        """
        self.override_store.revert(target_id)

    def diff(self) -> str:
        """Generate unified diff across all applied overrides.
        Example:
            >>> g = Graph()
            >>> store = OverrideStore()
            >>> tools = EditTools(g, store)
            >>> tools.diff()
            ''
        """
        return self.override_store.to_diff()
