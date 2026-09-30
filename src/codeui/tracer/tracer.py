"""Logic, dependency, and call-graph path tracing."""
from typing import Dict, Iterable, List, Set
from codeui.core.graph import Graph
from codeui.core.ir import Edge, EdgeKind, LayerKind, Location, Symbol, SymbolKind, Visibility

class Tracer:
    """Traces forward and backward execution paths and symbol call chains.
    Example:
        >>> t = Tracer(Graph())
        >>> list(t.forward("missing"))
        []
    """
    TRACER_EDGE_KINDS = (
        EdgeKind.CALLS,
        EdgeKind.READS,
        EdgeKind.WRITES,
        EdgeKind.REFERENCES,
        EdgeKind.INSTANTIATES,
        EdgeKind.INHERITS,
        EdgeKind.IMPLEMENTS,
        EdgeKind.OVERRIDES,
        EdgeKind.DEPENDS_ON,
    )

    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def forward(self, symbol_id: str, depth: int = 5) -> Iterable[Symbol]:
        """Trace forward callers or dependents targeting the specified symbol.
        Example:
            >>> t = Tracer(Graph())
            >>> list(t.forward("s"))
            []
        """
        visited: Set[str] = {symbol_id}
        queue: List[str] = [symbol_id]
        current_depth = 0

        while queue and current_depth < depth:
            next_queue: List[str] = []
            for curr in queue:
                for edge in self.graph.get_incoming_edges(curr):
                    if edge.kind in self.TRACER_EDGE_KINDS:
                        src = edge.source_id
                        if src not in visited:
                            visited.add(src)
                            if self.graph.has_symbol(src):
                                sym = self.graph.get_symbol(src)
                                yield sym
                                next_queue.append(src)
            queue = next_queue
            current_depth += 1

    def backward(self, symbol_id: str, depth: int = 5) -> Iterable[Symbol]:
        """Trace backward downstream dependencies and callees invoked by symbol.
        Example:
            >>> t = Tracer(Graph())
            >>> list(t.backward("s"))
            []
        """
        visited: Set[str] = {symbol_id}
        queue: List[str] = [symbol_id]
        current_depth = 0

        while queue and current_depth < depth:
            next_queue: List[str] = []
            for curr in queue:
                for edge in self.graph.get_outgoing_edges(curr):
                    if edge.kind in self.TRACER_EDGE_KINDS:
                        tgt = edge.target_id
                        if tgt not in visited:
                            visited.add(tgt)
                            if self.graph.has_symbol(tgt):
                                sym = self.graph.get_symbol(tgt)
                                yield sym
                                next_queue.append(tgt)
            queue = next_queue
            current_depth += 1

    def entry_points(self) -> Iterable[Symbol]:
        """Yield symbols that act as project entry points based on file classification or explicit entries.
        Example:
            >>> t = Tracer(Graph())
            >>> list(t.entry_points())
            []
        """
        explicit = getattr(self.graph, "_entry_points", [])
        if explicit:
            clean_entries = [e.replace("\\", "/").strip().lstrip("./") for e in explicit]
            for s in self.graph.get_all_symbols():
                if s.location and s.location.file_id:
                    clean_f = s.location.file_id.replace("\\", "/").strip().lstrip("./")
                    if clean_f in clean_entries:
                        yield s
            return

        for s in self.graph.get_all_symbols():
            if s.location and s.location.file_id:
                cls = self.graph.get_file_classification(s.location.file_id)
                if cls.layer == LayerKind.ENTRY:
                    yield s

    def find_path(self, source_id: str, target_id: str, max_depth: int = 15) -> List[str]:
        """Find the shortest directed dependency or call path between two nodes.
        Example:
            >>> g = Graph()
            >>> loc = Location("a.py", 1, 0, 1, 0)
            >>> g.add_symbol(Symbol("s1", "f1", "a.f1", SymbolKind.FUNCTION, "py", loc, None, None, Visibility.PUBLIC, (), "h1"))
            >>> g.add_symbol(Symbol("s2", "f2", "a.f2", SymbolKind.FUNCTION, "py", loc, None, None, Visibility.PUBLIC, (), "h2"))
            >>> g.add_edge(Edge("s1", "s2", EdgeKind.CALLS, 1.0, 1.0, loc))
            >>> t = Tracer(g)
            >>> t.find_path("s1", "s2")
            ['s1', 's2']
        """
        if not source_id or not target_id:
            return []
        if source_id == target_id:
            return [source_id]

        queue: List[List[str]] = [[source_id]]
        visited: Set[str] = {source_id}

        while queue:
            path = queue.pop(0)
            if len(path) > max_depth:
                continue
            curr = path[-1]
            for edge in self.graph.get_outgoing_edges(curr):
                if edge.kind == EdgeKind.CONTAINS:
                    continue
                nxt = edge.target_id
                if nxt == target_id:
                    return path + [nxt]
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(path + [nxt])

        return []
