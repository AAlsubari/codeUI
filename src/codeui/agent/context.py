"""Dynamic context builder for AI agents based on graph structure."""
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple
from codeui.core.graph import Graph
from codeui.core.ir import Edge, Finding, Symbol
from codeui.errors import SymbolNotFoundError, FileNotFoundInGraphError

@dataclass
class TaskSpec:
    """Specification of an AI agent coding task.
    Example:
        >>> spec = TaskSpec("Fix bug in main", ["sym_1"], ["app.py"])
        >>> spec.query
        'Fix bug in main'
    """
    query: str
    target_symbols: List[str] = field(default_factory=list)
    target_files: List[str] = field(default_factory=list)

@dataclass
class ContextBundle:
    """Compact context payload for LLMs built via graph structure.
    Example:
        >>> bundle = ContextBundle({"sym_1": "def f(): pass"}, {"sym_2": "def g():"}, [], [], {"reason": "test"})
        >>> bundle.manifest["reason"]
        'test'
    """
    symbol_bodies: Dict[str, str]
    cross_signatures: Dict[str, str]
    edge_summaries: List[Dict[str, Any]]
    findings: List[Dict[str, Any]]
    manifest: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert context bundle to dictionary.
        Example:
            >>> bundle = ContextBundle({}, {}, [], [], {})
            >>> "symbol_bodies" in bundle.to_dict()
            True
        """
        return asdict(self)

    def to_json(self) -> str:
        """Convert context bundle to deterministic JSON string.
        Example:
            >>> bundle = ContextBundle({}, {}, [], [], {})
            >>> isinstance(bundle.to_json(), str)
            True
        """
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

class ContextBuilder:
    """Builds structured dynamic context bundles from graph traversal.
    Example:
        >>> g = Graph()
        >>> builder = ContextBuilder(g)
        >>> bundle = builder.for_symbol("sym_1", 1)
        >>> bundle.manifest["status"]
        'empty'
    """
    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    @staticmethod
    def _comment_prefix(file_id: str) -> str:
        lower = file_id.lower()
        if lower.endswith((".py", ".pyi", ".sh", ".bash", ".zsh", ".yaml", ".yml", ".toml", ".rb")):
            return "#"
        if lower.endswith((".sql", ".lua")):
            return "--"
        return "//"

    def for_symbol(self, symbol_id: str, depth: int = 1, seen_hashes: Set[str] | None = None) -> ContextBundle:
        """Build context bundle starting from a symbol outwards by N hops.
        Example:
            >>> g = Graph()
            >>> builder = ContextBuilder(g)
            >>> bundle = builder.for_symbol("sym_1", 1)
            >>> "symbol_id" in bundle.manifest
            True
        """
        seen_hashes = seen_hashes or set()
        if not self.graph.has_symbol(symbol_id):
            return ContextBundle(
                symbol_bodies={},
                cross_signatures={},
                edge_summaries=[],
                findings=[],
                manifest={"symbol_id": symbol_id, "status": "empty", "reason": "symbol_not_found"},
            )
        syms, edges = self.graph.get_subgraph(symbol_id, depth=depth)
        target_sym = self.graph.get_symbol(symbol_id)
        bodies: Dict[str, str] = {}
        signatures: Dict[str, str] = {}
        for s in syms:
            if s.content_hash in seen_hashes:
                continue
            f_id = s.location.file_id if s.location else ""
            cm = self._comment_prefix(f_id)
            if s.id == symbol_id:
                bodies[s.id] = f"{cm} {f_id}:{s.location.start_line if s.location else 1}\n{s.signature or s.name}"
            else:
                signatures[s.id] = s.signature or f"{s.kind} {s.name}"

        edge_summaries = [
            {"source": e.source_id, "target": e.target_id, "kind": str(e.kind)}
            for e in edges
        ]

        relevant_findings = [
            f.to_dict() for f in self.graph.get_findings()
            if f.symbol_id in {s.id for s in syms} or f.location.file_id == target_sym.location.file_id
        ]

        manifest = {
            "symbol_id": symbol_id,
            "depth": depth,
            "symbols_included": len(syms),
            "edges_included": len(edges),
            "findings_included": len(relevant_findings),
            "status": "success",
        }
        return ContextBundle(
            symbol_bodies=bodies,
            cross_signatures=signatures,
            edge_summaries=edge_summaries,
            findings=relevant_findings,
            manifest=manifest,
        )

    def for_file(self, file_id: str, depth: int = 1, seen_hashes: Set[str] | None = None) -> ContextBundle:
        """Build context bundle for all symbols in a file.
        Example:
            >>> g = Graph()
            >>> builder = ContextBuilder(g)
            >>> bundle = builder.for_file("app.py", 1)
            >>> bundle.manifest["file_id"]
            'app.py'
        """
        seen_hashes = seen_hashes or set()
        symbols = self.graph.get_symbols_by_file(file_id)
        bodies: Dict[str, str] = {}
        cm = self._comment_prefix(file_id)
        for s in symbols:
            if s.content_hash not in seen_hashes:
                bodies[s.id] = f"{cm} {file_id}:{s.location.start_line if s.location else 1}\n{s.signature or s.name}"
        relevant_findings = [
            f.to_dict() for f in self.graph.get_findings()
            if f.location.file_id == file_id
        ]
        return ContextBundle(
            symbol_bodies=bodies,
            cross_signatures={},
            edge_summaries=[],
            findings=relevant_findings,
            manifest={"file_id": file_id, "symbols_count": len(symbols), "status": "success"},
        )

    def for_task(self, task: TaskSpec, depth: int = 1) -> ContextBundle:
        """Build context bundle tailored to a task specification.
        Example:
            >>> g = Graph()
            >>> builder = ContextBuilder(g)
            >>> spec = TaskSpec("Fix issue")
            >>> bundle = builder.for_task(spec)
            >>> "query" in bundle.manifest
            True
        """
        combined_bodies: Dict[str, str] = {}
        combined_sigs: Dict[str, str] = {}
        combined_edges: List[Dict[str, Any]] = []
        combined_findings: List[Dict[str, Any]] = []
        for sym_id in task.target_symbols:
            b = self.for_symbol(sym_id, depth=depth)
            combined_bodies.update(b.symbol_bodies)
            combined_sigs.update(b.cross_signatures)
            combined_edges.extend(b.edge_summaries)
            combined_findings.extend(b.findings)
        for file_id in task.target_files:
            b = self.for_file(file_id, depth=depth)
            combined_bodies.update(b.symbol_bodies)
            combined_findings.extend(b.findings)
        return ContextBundle(
            symbol_bodies=combined_bodies,
            cross_signatures=combined_sigs,
            edge_summaries=combined_edges,
            findings=combined_findings,
            manifest={"query": task.query, "symbols": task.target_symbols, "files": task.target_files},
        )

    def for_defect(self, finding_id: str) -> ContextBundle:
        """Build context bundle targeting a specific defect finding.
        Example:
            >>> g = Graph()
            >>> builder = ContextBuilder(g)
            >>> bundle = builder.for_defect("f1")
            >>> bundle.manifest["finding_id"]
            'f1'
        """
        matching = [f for f in self.graph.get_findings() if f.id == finding_id]
        if not matching:
            return ContextBundle({}, {}, [], [], {"finding_id": finding_id, "status": "not_found"})
        f = matching[0]
        if f.symbol_id:
            return self.for_symbol(f.symbol_id, depth=1)
        return self.for_file(f.location.file_id, depth=1)
