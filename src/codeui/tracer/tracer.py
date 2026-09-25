"""Logic and call-chain tracer across files and languages."""
import fnmatch
from collections import deque
from pathlib import Path
from typing import Generator, Iterable, List, Set, Tuple
from codeui.core.graph import Graph
from codeui.core.ir import Edge, EdgeKind, Symbol, SymbolKind
from codeui.errors import SymbolNotFoundError

class Tracer:
    """Graph logic tracer yielding call chains, data flow, and entry points.
    Example:
        >>> g = Graph()
        >>> tracer = Tracer(g)
        >>> list(tracer.entry_points())
        []
    """
    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def forward(self, symbol_id: str, depth: int | None = None) -> Generator[Symbol, None, None]:
        """Follow symbol usage forward (who uses or calls this symbol?).
        Example:
            >>> g = Graph()
            >>> tracer = Tracer(g)
            >>> list(tracer.forward("nonexistent", 1))
            []
        """
        if not self.graph.has_symbol(symbol_id):
            return
        visited: Set[str] = {symbol_id}
        queue: deque[Tuple[str, int]] = deque([(symbol_id, 0)])
        while queue:
            curr_id, curr_depth = queue.popleft()
            if depth is not None and curr_depth >= depth:
                continue
            incoming = self.graph.get_incoming_edges(curr_id)
            for edge in incoming:
                src_id = edge.source_id
                if src_id not in visited and self.graph.has_symbol(src_id):
                    visited.add(src_id)
                    queue.append((src_id, curr_depth + 1))
                    yield self.graph.get_symbol(src_id)

    def backward(self, symbol_id: str, depth: int | None = None) -> Generator[Symbol, None, None]:
        """Follow symbol dependencies backward (what does this symbol depend on?).
        Example:
            >>> g = Graph()
            >>> tracer = Tracer(g)
            >>> list(tracer.backward("nonexistent", 1))
            []
        """
        if not self.graph.has_symbol(symbol_id):
            return
        visited: Set[str] = {symbol_id}
        queue: deque[Tuple[str, int]] = deque([(symbol_id, 0)])
        while queue:
            curr_id, curr_depth = queue.popleft()
            if depth is not None and curr_depth >= depth:
                continue
            outgoing = self.graph.get_outgoing_edges(curr_id)
            for edge in outgoing:
                tgt_id = edge.target_id
                if tgt_id not in visited and self.graph.has_symbol(tgt_id):
                    visited.add(tgt_id)
                    queue.append((tgt_id, curr_depth + 1))
                    yield self.graph.get_symbol(tgt_id)

    def paths(self, from_id: str, to_id: str, max_paths: int = 5) -> Generator[List[Symbol], None, None]:
        """Find shortest call or reference paths between two symbols.
        Example:
            >>> g = Graph()
            >>> tracer = Tracer(g)
            >>> list(tracer.paths("a", "b", 5))
            []
        """
        if not self.graph.has_symbol(from_id) or not self.graph.has_symbol(to_id):
            return
        paths_found = 0
        queue: deque[List[str]] = deque([[from_id]])
        visited: Set[Tuple[str, ...]] = set()
        while queue and paths_found < max_paths:
            path = queue.popleft()
            last_node = path[-1]
            if last_node == to_id:
                paths_found += 1
                yield [self.graph.get_symbol(nid) for nid in path]
                continue
            for edge in self.graph.get_outgoing_edges(last_node):
                nxt = edge.target_id
                if nxt not in path and self.graph.has_symbol(nxt):
                    new_path = path + [nxt]
                    path_tuple = tuple(new_path)
                    if path_tuple not in visited:
                        visited.add(path_tuple)
                        queue.append(new_path)

    def data_flow(self, symbol_id: str) -> Generator[Tuple[Symbol, str], None, None]:
        """Trace definition-use data flow chains for a variable or parameter.
        Example:
            >>> g = Graph()
            >>> tracer = Tracer(g)
            >>> list(tracer.data_flow("s1"))
            []
        """
        if not self.graph.has_symbol(symbol_id):
            return
        for edge in self.graph.get_outgoing_edges(symbol_id):
            if edge.kind in (EdgeKind.READS, EdgeKind.WRITES, EdgeKind.RETURNS):
                if self.graph.has_symbol(edge.target_id):
                    yield (self.graph.get_symbol(edge.target_id), str(edge.kind))

    def entry_points(self) -> Generator[Symbol, None, None]:
        """Discover project entry point symbols across languages with user entry precedence.
        Example:
            >>> from codeui.core.ir import Location, Symbol, SymbolKind, Visibility
            >>> g = Graph()
            >>> g.set_entry_points(["custom_script.py"])
            >>> loc = Location("custom_script.py", 1, 0, 2, 0)
            >>> g.add_symbol(Symbol("custom_script.py::run", "run", "custom_script.run", SymbolKind.FUNCTION, "python", loc, None, "def run():", Visibility.PUBLIC, (), "h"))
            >>> tracer = Tracer(g)
            >>> [s.name for s in tracer.entry_points()]
            ['run']
        """
        if getattr(self.graph, "_entry_points", None):
            user_entries = [str(ep).replace("\\", "/").lstrip("./") for ep in self.graph._entry_points]
            yielded_ids = set()
            for sym in self.graph.get_all_symbols():
                f_id = (sym.location.file_id if sym.location else sym.id).replace("\\", "/").lstrip("./")
                is_match = False
                for ep in user_entries:
                    ep_sub = ep.split("/", 1)[1] if "/" in ep else ep
                    if f_id == ep or f_id == ep_sub or (any(c in ep for c in "*?[") and fnmatch.fnmatch(f_id, ep)):
                        is_match = True
                        break
                if is_match and sym.id not in yielded_ids:
                    yielded_ids.add(sym.id)
                    yield sym
            if yielded_ids:
                return

        entry_names = {"main", "index", "App", "app", "run", "handler", "cli", "start", "init", "__main__"}
        for sym in self.graph.get_all_symbols():
            if sym.kind in (SymbolKind.FUNCTION, SymbolKind.FILE) and not sym.name.startswith("test_") and (
                sym.name in entry_names or any(sym.name.startswith(p) for p in ("start_", "run_", "main_")) or sym.id.endswith("main.py") or sym.id.endswith("main.go") or sym.id.endswith("main.rs") or sym.id.endswith("index.ts") or sym.id.endswith("index.js")
            ):
                yield sym
