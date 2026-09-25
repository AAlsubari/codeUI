"""LangChain, LlamaIndex, and MCP tool integration helpers."""
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from codeui.agent.context import ContextBuilder
from codeui.agent.contribution import ContributionManager
from codeui.agent.edit_tools import EditProposal, EditTools
from codeui.core.graph import Graph
from codeui.core.override import OverrideStore
from codeui.core.repo import get_library_repo_url
from codeui.tracer.tracer import Tracer

class CodeUITools:
    """Unified integration tools exposing codeui capabilities to AI agents.
    Example:
        >>> g = Graph()
        >>> tools = CodeUITools(g)
        >>> "matches" in tools.find_symbol("main")
        True
    """
    def __init__(
        self,
        graph: Graph,
        override_store: Optional[OverrideStore] = None,
        project_root: Optional[Union[str, Path]] = None,
        direct_disk: bool = True,
    ) -> None:
        self.graph = graph
        self.override_store = override_store or OverrideStore()
        self.project_root = Path(project_root).resolve() if project_root else None
        self.direct_disk = direct_disk
        self.tracer = Tracer(graph)
        self.context_builder = ContextBuilder(graph)
        self.edit_tools = EditTools(
            graph=graph,
            override_store=self.override_store,
            project_root=self.project_root,
            direct_disk=self.direct_disk,
        )

    def find_symbol(self, query: str) -> Dict[str, Any]:
        """Search for symbols by name or qualified name.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> tools.find_symbol("f")["matches"]
            []
        """
        matches = [
            s.to_dict() for s in self.graph.get_all_symbols()
            if query.lower() in s.name.lower() or query.lower() in s.qualified_name.lower()
        ]
        return {"query": query, "matches": matches, "count": len(matches)}

    def get_context(self, symbol_id: str, depth: int = 1) -> Dict[str, Any]:
        """Retrieve graph-based context bundle for symbol.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> "manifest" in tools.get_context("sym_1")
            True
        """
        bundle = self.context_builder.for_symbol(symbol_id, depth=depth)
        return bundle.to_dict()

    def find_defects(self, severity: str | None = None) -> Dict[str, Any]:
        """Fetch all defects filtered by optional severity.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> tools.find_defects()["count"]
            0
        """
        findings = self.graph.get_findings()
        if severity:
            findings = [f for f in findings if str(f.severity) == severity]
        return {"findings": [f.to_dict() for f in findings], "count": len(findings)}

    def trace_call_chain(self, symbol_id: str, direction: str = "forward", depth: int = 3) -> Dict[str, Any]:
        """Trace symbol call chain forward or backward.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> tools.trace_call_chain("sym_1")["chain"]
            []
        """
        if direction == "backward":
            chain = [s.to_dict() for s in self.tracer.backward(symbol_id, depth=depth)]
        else:
            chain = [s.to_dict() for s in self.tracer.forward(symbol_id, depth=depth)]
        return {"symbol_id": symbol_id, "direction": direction, "chain": chain}

    def propose_rename(self, symbol_id: str, new_name: str) -> Dict[str, Any]:
        """Propose renaming a symbol and preview diff.
        Example:
            >>> from codeui.core.ir import Location, Symbol, SymbolKind, Visibility
            >>> g = Graph()
            >>> loc = Location("a.py", 1, 0, 1, 0)
            >>> g.add_symbol(Symbol("s1", "f", "a.f", SymbolKind.FUNCTION, "python", loc, None, None, Visibility.PUBLIC, (), "h"))
            >>> tools = CodeUITools(g)
            >>> tools.propose_rename("s1", "new_f")["target_id"]
            's1'
        """
        proposal = self.edit_tools.rename_symbol(symbol_id, new_name)
        return proposal.to_dict()

    def propose_replace_file(self, file_id: str, new_content: str, original_content: str = "") -> Dict[str, Any]:
        """Propose replacing file content.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> tools.propose_replace_file("a.py", "x = 1")["target_id"]
            'a.py'
        """
        proposal = self.edit_tools.replace_file(file_id, new_content, original_content)
        return proposal.to_dict()

    def write_file_direct(self, file_id: str, new_content: str) -> Dict[str, Any]:
        """Directly write content to a project file on disk.
        Example:
            >>> import tempfile
            >>> with tempfile.TemporaryDirectory() as td:
            ...     tools = CodeUITools(Graph(), project_root=td)
            ...     res = tools.write_file_direct("main.py", "print('hello')")
            ...     res["status"]
            'saved_to_disk'
        """
        path = self.edit_tools.write_file_to_disk(file_id, new_content)
        return {"status": "saved_to_disk", "file_id": file_id, "path": str(path)}

    def apply_proposal(
        self,
        proposal: Dict[str, Any],
        author: str = "agent",
        direct_disk: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Apply an edit proposal into the active override store or directly to project file on disk.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g, direct_disk=False)
            >>> prop = tools.propose_replace_file("a.py", "x = 1")
            >>> tools.apply_proposal(prop)["status"]
            'applied'
        """
        prop_obj = EditProposal(
            target_id=proposal["target_id"],
            kind=proposal["kind"],
            affected_symbols=proposal.get("affected_symbols", []),
            affected_files=proposal.get("affected_files", []),
            diff_preview=proposal.get("diff_preview", ""),
            conflicts=[],
            new_value=proposal.get("new_value"),
        )
        self.edit_tools.apply(prop_obj, author=author, write_to_disk=direct_disk)
        status = "written_to_disk" if (direct_disk or (direct_disk is None and self.direct_disk and self.project_root is not None)) else "applied"
        return {"status": status, "target_id": proposal["target_id"]}

    def revert_override(self, target_id: str) -> Dict[str, Any]:
        """Revert active override for target symbol or file.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> tools.revert_override("a.py")["status"]
            'reverted'
        """
        self.edit_tools.revert(target_id)
        return {"status": "reverted", "target_id": target_id}

    def diff(self) -> str:
        """Get unified diff across all active overrides.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> tools.get_diff()
            ''
        """
        return self.edit_tools.diff()

    def get_diff(self) -> str:
        """Get unified diff across all active overrides.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> tools.get_diff()
            ''
        """
        return self.edit_tools.diff()

    def get_repository_url(self) -> str:
        """Retrieve the official codeui GitHub repository URL.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> tools.get_repository_url()
            'https://github.com/AAlsubari/codeUI'
        """
        return get_library_repo_url()

    def clone_library_repository(
        self,
        target_dir: Optional[Union[str, Path]] = None,
        token: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Clone the codeui repository for inspection, bug fixing, or feature addition.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> tools.get_repository_url()
            'https://github.com/AAlsubari/codeUI'
        """
        mgr = ContributionManager(token=token)
        cloned_path = mgr.clone_repository(target_dir=target_dir, token=token, branch=branch)
        return {
            "status": "cloned",
            "repo_url": mgr.get_repo_url(),
            "cloned_dir": str(cloned_path),
        }

    def submit_library_contribution(
        self,
        title: str,
        description: str,
        file_changes: Dict[str, str],
        branch_name: Optional[str] = None,
        token: Optional[str] = None,
        push: bool = True,
    ) -> Dict[str, Any]:
        """Clone codeui, apply modifications (bug fixes / features), commit, and push to GitHub.
        Example:
            >>> g = Graph()
            >>> tools = CodeUITools(g)
            >>> tools.get_repository_url()
            'https://github.com/AAlsubari/codeUI'
        """
        mgr = ContributionManager(token=token)
        return mgr.submit_contribution(
            title=title,
            description=description,
            file_changes=file_changes,
            branch_name=branch_name,
            token=token,
            push=push,
        )
