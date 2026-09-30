"""In-memory universal code graph store."""
import fnmatch
import json
from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from codeui.core.ir import Edge, EdgeKind, FileClassification, Finding, LayerKind, Location, Severity, Symbol, SymbolKind, Visibility
from codeui.errors import SymbolNotFoundError, FileNotFoundInGraphError

def classify_file(file_path: str, entry_points: Optional[Iterable[str]] = None, layer_rules: Optional[Dict[str, Any]] = None) -> FileClassification:
    """Classify a file path into architectural layer, feature, and module.
    Example:
        >>> c = classify_file("src/components/auth/LoginModal.tsx")
        >>> str(c.layer)
        'frontend'
        >>> c.feature
        'components/auth'
        >>> c2 = classify_file("custom/path/app.py", entry_points=["custom/path/app.py"])
        >>> str(c2.layer)
        'entry'
    """
    clean_path = file_path.replace("\\", "/").lstrip("./")
    parts = [p for p in clean_path.split("/") if p]
    if not parts:
        return FileClassification(LayerKind.OTHER, "root", "root")

    filename = parts[-1]
    name_lower = filename.lower()
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    stem_lower = stem.lower()
    parts_lower = [p.lower() for p in parts]

    if entry_points:
        clean_entries = [str(ep).replace("\\", "/").lstrip("./") for ep in entry_points]
        for ep in clean_entries:
            ep_sub = ep.split("/", 1)[1] if "/" in ep else ep
            is_entry_match = (
                clean_path == ep
                or clean_path == ep_sub
                or (any(c in ep for c in "*?[") and fnmatch.fnmatch(clean_path, ep))
            )
            if is_entry_match:
                return FileClassification(LayerKind.ENTRY, "app_entry", parts[0] if len(parts) > 1 else "root")

    if any(p in ("tests", "test", "__tests__", "spec", "specs", "benchmarks") for p in parts_lower) or any(name_lower.endswith(s) for s in (".test.ts", ".test.tsx", ".test.js", ".test.jsx", ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx", "_test.py", "_test.go", "_spec.rb", "_test.rs")):
        return FileClassification(LayerKind.TEST, "test", "test")

    if filename in ("tsconfig.json", "package.json", "pyproject.toml", "vite.config.ts", "vite.config.js", "webpack.config.js", "Cargo.toml", "go.mod", "Makefile", "Dockerfile", ".codeui.json", "codeui.json") or filename.startswith("."):
        return FileClassification(LayerKind.CONFIG, "config", "config")

    entry_stems = {"__main__", "main", "app", "cli", "run", "entry", "start", "server"}
    is_root_level = len(parts) <= 1 or (len(parts) == 2 and parts[0] in ("src", "cmd", "bin", "app"))
    is_entry = (
        (stem_lower in entry_stems and is_root_level)
        or (filename in ("__main__.py", "main.py", "main.go", "main.rs", "main.ts", "main.js", "index.ts", "index.js", "index.tsx", "index.jsx", "app.py", "app.ts", "app.tsx", "app.js") and is_root_level)
        or (stem_lower.endswith("_entry") or stem_lower.endswith("_main"))
    )

    if is_entry:
        return FileClassification(LayerKind.ENTRY, "app_entry", parts[0] if len(parts) > 1 else "root")

    content_parts = parts[1:] if len(parts) > 1 and parts[0].lower() in ("src", "pkg", "crates", "services", "apps", "packages", "libs", "cmd", "internal", "modules") else parts
    module = content_parts[0] if len(content_parts) > 1 else ("root" if len(parts) == 1 else parts[0])

    if len(content_parts) > 1:
        feature = "/".join(content_parts[:-1])
    else:
        feature = "app_entry" if is_entry else "root"

    if layer_rules:
        for layer_str, patterns in layer_rules.items():
            if isinstance(patterns, (list, tuple, set)):
                for pattern in patterns:
                    pat_clean = str(pattern).replace("\\", "/").lstrip("./").lower()
                    pat_base = pat_clean.rstrip("/*").rstrip("*")
                    is_match = (
                        pat_clean == clean_path.lower()
                        or (any(c in pat_clean for c in "*?[") and fnmatch.fnmatch(clean_path.lower(), pat_clean))
                        or (pat_base and (clean_path.lower().startswith(pat_base + "/") or clean_path.lower() == pat_base))
                        or (len(parts) > 1 and any(p.lower() == pat_base for p in parts[:-1]))
                    )
                    if is_match:
                        try:
                            lk = LayerKind(layer_str)
                            return FileClassification(lk, feature, module)
                        except ValueError:
                            pass

    shared_kw = {"utils", "util", "common", "shared", "helpers", "helper", "types", "constants", "errors", "exceptions"}
    hooks_kw = {"hooks", "composables"}
    frontend_kw = {"components", "screens", "views", "pages", "features", "ui", "frontend", "styles", "widgets", "assets", "static", "public", "templates", "client", "web"}
    backend_kw = {"server", "services", "service", "api", "backend", "domain", "data", "db", "models", "model", "controllers", "controller", "routes", "route", "handler", "handlers", "repository", "queries", "libraries", "srv", "analysis", "report", "plugins", "lang", "tracer", "agent","lib"}

    is_hook_stem = (stem.startswith("use") and len(stem) > 3 and stem[3].isupper() and name_lower.endswith((".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"))) or (stem.startswith("use_") and name_lower.endswith(".py") and any(p in ("hooks", "composables") for p in parts_lower))

    layer = LayerKind.OTHER
    if any(p in shared_kw for p in parts_lower[:-1]) or stem_lower in shared_kw:
        layer = LayerKind.SHARED
    elif any(p in hooks_kw for p in parts_lower[:-1]) or is_hook_stem:
        layer = LayerKind.HOOKS
    elif any(p in frontend_kw for p in parts_lower[:-1]) or stem_lower in ("button", "modal", "card", "view", "page", "screen", "layout", "canvas", "sidebar") or name_lower.endswith((".css", ".scss", ".less", ".html", ".jsx", ".tsx", ".vue", ".svelte")):
        layer = LayerKind.FRONTEND
    elif any(p in backend_kw for p in parts_lower[:-1]) or stem_lower in ("server", "daemon", "service", "api", "routes", "db", "models", "controller", "handler", "backend", "tracer", "context", "graph", "resolver", "runner"):
        layer = LayerKind.BACKEND
    elif is_entry:
        layer = LayerKind.ENTRY

    if layer == LayerKind.ENTRY:
        feature = "app_entry"

    return FileClassification(layer=layer, feature=feature, module=module)

class Graph:
    """Universal code graph storing symbols, edges, and findings.
    Example:
        >>> g = Graph()
        >>> loc = Location("main.py", 1, 0, 2, 0)
        >>> s = Symbol("s1", "main", "main.main", SymbolKind.FUNCTION, "python", loc, None, "def main():", Visibility.PUBLIC, (), "h1")
        >>> g.add_symbol(s)
        >>> g.get_symbol("s1").name
        'main'
    """
    def __init__(self) -> None:
        self._symbols: Dict[str, Symbol] = {}
        self._edges: List[Edge] = []
        self._edge_keys: Set[Tuple[str, str, str]] = set()
        self._out_edges: Dict[str, List[Edge]] = {}
        self._in_edges: Dict[str, List[Edge]] = {}
        self._file_symbols: Dict[str, Set[str]] = {}
        self._findings: List[Finding] = []
        self._entry_points: Set[str] = set()
        self._layer_rules: Dict[str, Any] = {}

    def set_entry_points(self, entry_points: Iterable[str]) -> None:
        """Set user-specified application entry points.
        Example:
            >>> g = Graph()
            >>> g.set_entry_points(["codeui/__init__.py"])
            >>> "codeui/__init__.py" in g._entry_points
            True
        """
        self._entry_points = {str(ep).replace("\\", "/").lstrip("./") for ep in entry_points}

    def set_layer_rules(self, rules: Dict[str, Any]) -> None:
        """Set user-specified layer classification rules.
        Example:
            >>> g = Graph()
            >>> g.set_layer_rules({"frontend": ["ui/*"]})
            >>> "frontend" in g._layer_rules
            True
        """
        self._layer_rules = dict(rules)

    def add_symbol(self, symbol: Symbol) -> None:
        """Add or replace a symbol in the graph.
        Example:
            >>> g = Graph()
            >>> loc = Location("a.py", 1, 0, 2, 0)
            >>> s = Symbol("s1", "f", "a.f", SymbolKind.FUNCTION, "python", loc, None, None, Visibility.PUBLIC, (), "h")
            >>> g.add_symbol(s)
            >>> g.has_symbol("s1")
            True
        """
        file_id = symbol.location.file_id if symbol.location else ""
        file_lower = file_id.lower()
        if "__pycache__" in file_lower or ".pytest_cache" in file_lower or file_lower.endswith((".pyc", ".pyo", ".pyd")):
            return
        self._symbols[symbol.id] = symbol
        if file_id not in self._file_symbols:
            self._file_symbols[file_id] = set()
        self._file_symbols[file_id].add(symbol.id)

    def remove_file_symbols(self, file_id: str) -> None:
        """Remove all symbols and associated edges for a file.
        Example:
            >>> g = Graph()
            >>> loc = Location("a.py", 1, 0, 2, 0)
            >>> s = Symbol("s1", "f", "a.f", SymbolKind.FUNCTION, "python", loc, None, None, Visibility.PUBLIC, (), "h")
            >>> g.add_symbol(s)
            >>> g.remove_file_symbols("a.py")
            >>> g.has_symbol("s1")
            False
        """
        symbol_ids = self._file_symbols.pop(file_id, set())
        for sym_id in symbol_ids:
            self._symbols.pop(sym_id, None)
            self._out_edges.pop(sym_id, None)
            self._in_edges.pop(sym_id, None)
        self._edges = [
            e for e in self._edges
            if e.source_id not in symbol_ids and e.target_id not in symbol_ids
        ]
        self._rebuild_edge_indexes()

    def add_edge(self, edge: Edge) -> None:
        """Add a directed edge between symbols.
        Example:
            >>> g = Graph()
            >>> edge = Edge("s1", "s2", EdgeKind.CALLS, 1.0, 1.0, None)
            >>> g.add_edge(edge)
            >>> len(g.get_edges())
            1
        """
        s_lower = edge.source_id.lower()
        t_lower = edge.target_id.lower()
        if "__pycache__" in s_lower or "__pycache__" in t_lower or s_lower.endswith((".pyc", ".pyo", ".pyd")) or t_lower.endswith((".pyc", ".pyo", ".pyd")):
            return
        key = (edge.source_id, edge.target_id, str(edge.kind))
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self._edges.append(edge)
        self._out_edges.setdefault(edge.source_id, []).append(edge)
        self._in_edges.setdefault(edge.target_id, []).append(edge)

    def add_finding(self, finding: Finding) -> None:
        """Add a defect finding to the graph.
        Example:
            >>> g = Graph()
            >>> loc = Location("a.py", 1, 0, 1, 5)
            >>> f = Finding("f1", "rule1", "msg", Severity.ERROR, loc, None, None, 1.0)
            >>> g.add_finding(f)
            >>> len(g.get_findings())
            1
        """
        self._findings.append(finding)

    def get_findings(self) -> List[Finding]:
        """Return all findings sorted deterministically.
        Example:
            >>> g = Graph()
            >>> g.get_findings()
            []
        """
        return sorted(self._findings, key=lambda f: f.id)

    def get_symbol(self, symbol_id: str) -> Symbol:
        """Fetch symbol by ID or raise SymbolNotFoundError.
        Example:
            >>> g = Graph()
            >>> loc = Location("a.py", 1, 0, 2, 0)
            >>> g.add_symbol(Symbol("s1", "f", "a.f", SymbolKind.FUNCTION, "py", loc, None, None, Visibility.PUBLIC, (), "h"))
            >>> g.get_symbol("s1").name
            'f'
        """
        if symbol_id not in self._symbols:
            raise SymbolNotFoundError(symbol_id)
        return self._symbols[symbol_id]

    def has_symbol(self, symbol_id: str) -> bool:
        """Check if symbol exists.
        Example:
            >>> g = Graph()
            >>> g.has_symbol("missing")
            False
        """
        return symbol_id in self._symbols

    def get_symbols(self) -> List[Symbol]:
        """Return list of all symbols in the graph.
        Example:
            >>> g = Graph()
            >>> g.get_symbols()
            []
        """
        return self.get_all_symbols()

    def get_all_symbols(self) -> List[Symbol]:
        """Return all symbols sorted deterministically by ID.
        Example:
            >>> g = Graph()
            >>> g.get_all_symbols()
            []
        """
        return sorted(self._symbols.values(), key=lambda s: s.id)

    def get_symbols_by_file(self, file_id: str) -> List[Symbol]:
        """Return all symbols belonging to a specific file.
        Example:
            >>> g = Graph()
            >>> g.get_symbols_by_file("nonexistent.py")
            []
        """
        sym_ids = self._file_symbols.get(file_id)
        if sym_ids is None:
            clean = file_id.replace("\\", "/").lstrip("./")
            for k, v in self._file_symbols.items():
                k_clean = k.replace("\\", "/").lstrip("./")
                if k_clean == clean or k_clean.endswith(clean) or clean.endswith(k_clean):
                    sym_ids = v
                    break
        if not sym_ids:
            return []
        symbols = [self._symbols[sid] for sid in sym_ids if sid in self._symbols]
        return sorted(symbols, key=lambda s: (s.location.start_line if s.location else 0, s.id))

    def has_file(self, file_id: str) -> bool:
        """Check if file exists in the code graph.
        Example:
            >>> g = Graph()
            >>> g.has_file("main.py")
            False
        """
        clean = file_id.replace("\\", "/").lstrip("./")
        for f in self._file_symbols:
            if f.replace("\\", "/").lstrip("./") == clean or f == file_id:
                return True
        return False

    def get_all_files(self) -> List[str]:
        """Return list of all analyzed file paths sorted.
        Example:
            >>> g = Graph()
            >>> g.get_all_files()
            []
        """
        return sorted(list(self._file_symbols.keys()))

    def get_edges(self) -> List[Edge]:
        """Return all graph edges sorted deterministically.
        Example:
            >>> g = Graph()
            >>> g.get_edges()
            []
        """
        return sorted(self._edges, key=lambda e: (e.source_id, e.target_id, str(e.kind)))

    def get_all_edges(self) -> List[Edge]:
        """Return all graph edges sorted deterministically (alias for get_edges).
        Example:
            >>> g = Graph()
            >>> g.get_all_edges()
            []
        """
        return self.get_edges()

    def get_outgoing_edges(self, source_id: str, kind: EdgeKind | None = None) -> List[Edge]:
        """Return outgoing edges from source symbol.
        Example:
            >>> g = Graph()
            >>> g.get_outgoing_edges("s1")
            []
        """
        edges = self._out_edges.get(source_id, [])
        if kind is not None:
            edges = [e for e in edges if e.kind == kind]
        return sorted(edges, key=lambda e: (e.target_id, str(e.kind)))

    def get_incoming_edges(self, target_id: str, kind: EdgeKind | None = None) -> List[Edge]:
        """Return incoming edges targeting symbol.
        Example:
            >>> g = Graph()
            >>> g.get_incoming_edges("s2")
            []
        """
        edges = self._in_edges.get(target_id, [])
        if kind is not None:
            edges = [e for e in edges if e.kind == kind]
        return sorted(edges, key=lambda e: (e.source_id, e.target_id, str(e.kind)))

    def get_file_subgraph(self, target_id: str, include_cross: bool = True, max_hops: Optional[int] = None) -> Dict[str, Any]:
        """Extract a sub-graph for a file or external symbol containing its symbols and related cross-file connections.
        Example:
            >>> g = Graph()
            >>> loc = Location("app.py", 1, 0, 5, 0)
            >>> g.add_symbol(Symbol("app.py::main", "main", "main", SymbolKind.FUNCTION, "python", loc, None, "def main()", Visibility.PUBLIC, (), "h1"))
            >>> res = g.get_file_subgraph("app.py")
            >>> res["file_id"]
            'app.py'
        """
        clean_target = target_id.replace("module::", "").replace("\\", "/").strip().lstrip("./")
        target_file: Optional[str] = None
        for f in self._file_symbols:
            if f.replace("\\", "/").lstrip("./") == clean_target or f == target_id:
                target_file = f
                break

        if not target_file and target_id in self._symbols:
            sym = self._symbols[target_id]
            if sym.location and sym.location.file_id:
                target_file = sym.location.file_id

        if not target_file:
            for s in self._symbols.values():
                if s.id == target_id or s.name == clean_target or s.qualified_name == clean_target or s.id.endswith("::" + clean_target):
                    if s.location and s.location.file_id:
                        target_file = s.location.file_id
                        break

        if target_file and target_file in self._file_symbols:
            raw_symbols = self.get_symbols_by_file(target_file)
            symbols = [s for s in raw_symbols if s.kind not in (SymbolKind.FILE, SymbolKind.VARIABLE)]
            if not symbols:
                symbols = [s for s in raw_symbols if s.kind != SymbolKind.FILE]
            if not symbols:
                symbols = raw_symbols
            sym_ids = {s.id for s in symbols}
            cls = self.get_file_classification(target_file)

            intra_edges = [
                e for e in self._edges
                if (e.source_id in sym_ids or e.source_id == target_file) and (e.target_id in sym_ids or e.target_id == target_file)
            ]

            related_symbols_dict: Dict[str, Dict[str, Any]] = {}
            collected_cross_edges: Set[Tuple[str, str, str]] = set()
            ext_edges: List[Edge] = []

            if include_cross:
                frontier: Set[str] = set(sym_ids)
                visited_symbols: Set[str] = set(sym_ids)
                hops = 0
                max_traversal_hops = max_hops if max_hops is not None else 1000

                file_outgoing = self.get_outgoing_edges(target_file)
                file_incoming = self.get_incoming_edges(target_file)
                for e in file_outgoing + file_incoming:
                    endpoint = e.target_id if e.source_id == target_file else e.source_id
                    if endpoint in self._file_symbols and endpoint != target_file:
                        edge_key = (e.source_id, e.target_id, str(e.kind))
                        if edge_key not in collected_cross_edges:
                            collected_cross_edges.add(edge_key)
                            ext_edges.append(e)
                        if endpoint not in related_symbols_dict and endpoint not in sym_ids:
                            endpoint_name = endpoint.split("/")[-1]
                            cls_end = self.get_file_classification(endpoint)
                            related_symbols_dict[endpoint] = {
                                "id": endpoint,
                                "name": endpoint_name,
                                "qualified_name": endpoint,
                                "kind": "file",
                                "file_id": endpoint,
                                "layer": str(cls_end.layer.value if hasattr(cls_end.layer, "value") else cls_end.layer) if cls_end else "shared",
                                "feature": cls_end.feature if cls_end else "external",
                                "is_external": True,
                                "location": None,
                                "signature": None,
                            }

                while frontier and hops < max_traversal_hops:
                    next_frontier: Set[str] = set()
                    for current_id in frontier:
                        for e in self.get_outgoing_edges(current_id):
                            edge_key = (e.source_id, e.target_id, str(e.kind))
                            if e.target_id in self._symbols:
                                other_sym = self._symbols[e.target_id]
                                if other_sym.kind in (SymbolKind.FILE, SymbolKind.VARIABLE):
                                    continue
                                other_file = other_sym.location.file_id if other_sym.location else ""
                                if other_file and other_file in self._file_symbols:
                                    if other_file != target_file:
                                        if edge_key not in collected_cross_edges:
                                            collected_cross_edges.add(edge_key)
                                            ext_edges.append(e)
                                        if other_sym.id not in related_symbols_dict:
                                            other_cls = self.get_file_classification(other_file)
                                            related_symbols_dict[other_sym.id] = {
                                                "id": other_sym.id,
                                                "name": other_sym.name,
                                                "qualified_name": other_sym.qualified_name,
                                                "kind": str(other_sym.kind.value if hasattr(other_sym.kind, "value") else other_sym.kind),
                                                "file_id": other_file,
                                                "layer": str(other_cls.layer.value if hasattr(other_cls.layer, "value") else other_cls.layer) if other_cls else "shared",
                                                "feature": other_cls.feature if other_cls else "external",
                                                "is_external": True,
                                                "location": other_sym.location.to_dict() if other_sym.location else None,
                                                "signature": other_sym.signature,
                                            }
                                        if other_sym.id not in visited_symbols:
                                            visited_symbols.add(other_sym.id)
                                            next_frontier.add(other_sym.id)

                        for e in self.get_incoming_edges(current_id):
                            edge_key = (e.source_id, e.target_id, str(e.kind))
                            if e.source_id in self._symbols:
                                other_sym = self._symbols[e.source_id]
                                if other_sym.kind in (SymbolKind.FILE, SymbolKind.VARIABLE):
                                    continue
                                other_file = other_sym.location.file_id if other_sym.location else ""
                                if other_file and other_file in self._file_symbols:
                                    if other_file != target_file:
                                        if edge_key not in collected_cross_edges:
                                            collected_cross_edges.add(edge_key)
                                            ext_edges.append(e)
                                        if other_sym.id not in related_symbols_dict:
                                            other_cls = self.get_file_classification(other_file)
                                            related_symbols_dict[other_sym.id] = {
                                                "id": other_sym.id,
                                                "name": other_sym.name,
                                                "qualified_name": other_sym.qualified_name,
                                                "kind": str(other_sym.kind.value if hasattr(other_sym.kind, "value") else other_sym.kind),
                                                "file_id": other_file,
                                                "layer": str(other_cls.layer.value if hasattr(other_cls.layer, "value") else other_cls.layer) if other_cls else "shared",
                                                "feature": other_cls.feature if other_cls else "external",
                                                "is_external": True,
                                                "location": other_sym.location.to_dict() if other_sym.location else None,
                                                "signature": other_sym.signature,
                                            }
                                        if other_sym.id not in visited_symbols:
                                            visited_symbols.add(other_sym.id)
                                            next_frontier.add(other_sym.id)
                    frontier = next_frontier
                    hops += 1

                all_known_ids = sym_ids | set(related_symbols_dict.keys()) | {target_file}
                for e in self._edges:
                    edge_key = (e.source_id, e.target_id, str(e.kind))
                    if e.source_id in all_known_ids and e.target_id in all_known_ids:
                        if edge_key not in collected_cross_edges and (e.source_id not in sym_ids or e.target_id not in sym_ids):
                            collected_cross_edges.add(edge_key)
                            ext_edges.append(e)

            return {
                "file_id": target_file,
                "classification": cls.to_dict(),
                "symbols": [s.to_dict() for s in symbols],
                "related_symbols": list(related_symbols_dict.values()),
                "edges": [e.to_dict() for e in intra_edges + ext_edges],
            }

        ext_id = target_id
        sym_name = ext_id.split("::")[-1].split(".")[-1]
        incoming = [e for e in self._edges if e.target_id == ext_id or e.target_id.endswith("." + sym_name)]
        outgoing = [e for e in self._edges if e.source_id == ext_id or e.source_id.endswith("." + sym_name)]
        ext_edges = incoming + outgoing
        related_symbols = {}
        for e in ext_edges:
            endpoint = e.source_id if e.target_id == ext_id or e.target_id.endswith("." + sym_name) else e.target_id
            if endpoint in self._symbols:
                s = self._symbols[endpoint]
                related_symbols[endpoint] = {
                    "id": s.id,
                    "name": s.name,
                    "qualified_name": s.qualified_name,
                    "kind": str(s.kind.value if hasattr(s.kind, "value") else s.kind),
                    "file_id": s.location.file_id if s.location else "",
                    "location": s.location.to_dict() if s.location else None,
                    "signature": s.signature,
                    "is_external": False,
                }
        is_class = bool(sym_name and sym_name[0].isupper())
        return {
            "file_id": ext_id,
            "classification": {"layer": "shared", "feature": "external", "module": "external"},
            "is_external": True,
            "symbols": [{
                "id": ext_id,
                "name": sym_name,
                "qualified_name": ext_id,
                "kind": "class" if is_class else "function",
                "signature": f"{sym_name}(...)",
                "is_external": True,
            }],
            "related_symbols": list(related_symbols.values()),
            "edges": [e.to_dict() for e in ext_edges],
        }

    def get_subgraph(self, symbol_id: str, depth: int | None = None) -> Tuple[List[Symbol], List[Edge]]:
        """Extract a sub-graph surrounding a target symbol up to specified depth or all reachable nodes if depth is None.
        Example:
            >>> g = Graph()
            >>> loc = Location("a.py", 1, 0, 2, 0)
            >>> g.add_symbol(Symbol("s1", "f", "a.f", SymbolKind.FUNCTION, "py", loc, None, None, Visibility.PUBLIC, (), "h"))
            >>> syms, edges = g.get_subgraph("s1", 1)
            >>> len(syms)
            1
        """
        if symbol_id not in self._symbols:
            raise SymbolNotFoundError(symbol_id)
        visited_symbols: Set[str] = {symbol_id}
        frontier: Set[str] = {symbol_id}
        collected_edges: Set[Edge] = set()
        curr_depth = 0
        while frontier:
            if depth is not None and curr_depth >= depth:
                break
            next_frontier: Set[str] = set()
            for current_id in frontier:
                out_edges = self._out_edges.get(current_id, [])
                in_edges = self._in_edges.get(current_id, [])
                for e in out_edges:
                    collected_edges.add(e)
                    if e.target_id in self._symbols and e.target_id not in visited_symbols:
                        visited_symbols.add(e.target_id)
                        next_frontier.add(e.target_id)
                for e in in_edges:
                    collected_edges.add(e)
                    if e.source_id in self._symbols and e.source_id not in visited_symbols:
                        visited_symbols.add(e.source_id)
                        next_frontier.add(e.source_id)
            frontier = next_frontier
            curr_depth += 1
        symbols = [self._symbols[sid] for sid in sorted(visited_symbols)]
        edges = sorted(list(collected_edges), key=lambda e: (e.source_id, e.target_id, str(e.kind)))
        return symbols, edges

    def get_file_classification(self, file_id: str) -> FileClassification:
        """Return architectural classification for a specific file.
        Example:
            >>> g = Graph()
            >>> c = g.get_file_classification("src/components/Button.tsx")
            >>> str(c.layer)
            'frontend'
        """
        return classify_file(file_id, entry_points=self._entry_points, layer_rules=self._layer_rules)

    def get_files_info(self) -> Dict[str, Dict[str, Any]]:
        """Return detailed architectural information for all files in the graph.
        Example:
            >>> g = Graph()
            >>> loc = Location("a.py", 1, 0, 1, 10)
            >>> g.add_symbol(Symbol("a.py", "a.py", "a.py", SymbolKind.FILE, "python", loc, None, None, Visibility.PUBLIC, (), "h"))
            >>> info = g.get_files_info()
            >>> "a.py" in info
            True
        """
        result: Dict[str, Dict[str, Any]] = {}
        for file_id in self.get_all_files():
            classification = self.get_file_classification(file_id)
            syms = self.get_symbols_by_file(file_id)
            detected_symbols = [s for s in syms if s.kind not in (SymbolKind.FILE, SymbolKind.VARIABLE)]
            clean_path = file_id.replace("\\", "/").lstrip("./")
            parts = [p for p in clean_path.split("/") if p]
            folder = "/".join(parts[:-1]) if len(parts) > 1 else ""
            main_folder = parts[0] if len(parts) > 1 else "root"
            subfolder = parts[-2] if len(parts) > 2 else (parts[0] if len(parts) > 1 else "root")
            result[file_id] = {
                "path": file_id,
                "layer": str(classification.layer),
                "feature": classification.feature,
                "module": classification.module,
                "folder": folder,
                "main_folder": main_folder,
                "subfolder": subfolder,
                "symbol_count": len(detected_symbols),
                "symbols_count": len(detected_symbols),
                "total_symbols_count": len(syms),
                "symbol_ids": [s.id for s in syms],
                "detected_symbol_ids": [s.id for s in detected_symbols],
            }
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Convert graph state to deterministic JSON-serializable dictionary.
        Example:
            >>> g = Graph()
            >>> d = g.to_dict()
            >>> "symbols" in d and "edges" in d
            True
        """
        return {
            "symbols": [s.to_dict() for s in self.get_all_symbols()],
            "edges": [e.to_dict() for e in self.get_edges()],
            "findings": [f.to_dict() for f in self.get_findings()],
            "files": self.get_all_files(),
            "files_info": self.get_files_info(),
        }

    def _rebuild_edge_indexes(self) -> None:
        """Rebuild outgoing and incoming edge index maps."""
        self._out_edges.clear()
        self._in_edges.clear()
        self._edge_keys = {(e.source_id, e.target_id, str(e.kind)) for e in self._edges}
        for edge in self._edges:
            self._out_edges.setdefault(edge.source_id, []).append(edge)
            self._in_edges.setdefault(edge.target_id, []).append(edge)
