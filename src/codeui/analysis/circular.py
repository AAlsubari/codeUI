"""Circular import dependency analyzer."""
from pathlib import Path
from typing import ClassVar, Dict, Iterable, List, Set
from codeui.analysis.base import AnalysisContext, Analyzer
from codeui.core.graph import Graph
from codeui.core.ir import EdgeKind, Finding, Location, Severity

class CircularDependencyAnalyzer(Analyzer):
    """Detects cycles in the import graph.
    Example:
        >>> analyzer = CircularDependencyAnalyzer()
        >>> g = Graph()
        >>> ctx = AnalysisContext(Path("."))
        >>> list(analyzer.run(g, ctx))
        []
    """
    id: ClassVar[str] = "circular"
    severity_default: ClassVar[Severity] = Severity.ERROR

    def run(self, graph: Graph, ctx: AnalysisContext) -> Iterable[Finding]:
        """Detect circular import cycles using Tarjan's strongly connected components algorithm.
        Example:
            >>> analyzer = CircularDependencyAnalyzer()
            >>> g = Graph()
            >>> list(analyzer.run(g, AnalysisContext(Path("."))))
            []
        """
        all_files = set(graph.get_all_files())
        mod_to_file: Dict[str, str] = {}
        stem_map: Dict[str, List[str]] = {}

        for f in all_files:
            norm_f = f.replace("\\", "/")
            mod_to_file[norm_f] = norm_f
            dot_path = norm_f.replace("/", ".").rsplit(".", 1)[0]
            mod_to_file[dot_path] = norm_f
            stem_map.setdefault(Path(norm_f).stem, []).append(norm_f)

        all_sources = {e.source_id.replace("\\", "/") for e in graph.get_edges()}
        for s in all_sources:
            mod_to_file[s] = s
            dot_path = s.replace("/", ".").rsplit(".", 1)[0]
            mod_to_file[dot_path] = s
            stem_map.setdefault(Path(s).stem, []).append(s)

        for stem, file_list in stem_map.items():
            if len(file_list) == 1:
                mod_to_file[stem] = file_list[0]

        import_adj: Dict[str, Set[str]] = {}
        res_ctx = getattr(ctx, "resolve_context", None)
        if res_ctx is None and ctx and getattr(ctx, "root_dir", None):
            try:
                from codeui.core.resolver import ResolveContext
                res_ctx = ResolveContext(ctx.root_dir)
                res_ctx.set_known_files(all_files)
            except Exception:
                res_ctx = None

        for edge in graph.get_edges():
            if edge.kind == EdgeKind.IMPORTS:
                source = edge.source_id.replace("\\", "/")
                target_raw = edge.target_id.replace("module::", "").replace("\\", "/")
                resolved_target = mod_to_file.get(target_raw)
                if not resolved_target:
                    target_dot = target_raw.replace("/", ".")
                    resolved_target = mod_to_file.get(target_dot)
                if not resolved_target and "." in target_raw:
                    base = target_raw.rsplit(".", 1)[0]
                    resolved_target = mod_to_file.get(base)
                if not resolved_target:
                    stem = Path(target_raw).stem
                    resolved_target = mod_to_file.get(stem)
                if not resolved_target and res_ctx is not None:
                    try:
                        res_paths = res_ctx.resolve_path(source, target_raw, "generic")
                        if res_paths:
                            resolved_target = res_paths[0]
                    except Exception:
                        pass
                valid_modules = all_files | all_sources
                if resolved_target and resolved_target in valid_modules and resolved_target != source:
                    import_adj.setdefault(source, set()).add(resolved_target)

        findings: List[Finding] = []
        visited: Set[str] = set()
        rec_stack: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)
            for neighbor in import_adj.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    cycle_idx = rec_stack.index(neighbor)
                    cycle = rec_stack[cycle_idx:]
                    cycle_str = " -> ".join(cycle) + f" -> {neighbor}"
                    loc = Location(node, 1, 0, 1, 0)
                    finding = Finding(
                        id=f"circular::{cycle_str}",
                        rule_id="circular_dependency",
                        message=f"Circular import dependency detected: {cycle_str}",
                        severity=self.severity_default,
                        location=loc,
                        symbol_id=node,
                        fix_hint="Refactor shared types or functions into a separate common module",
                        confidence=0.95,
                    )
                    findings.append(finding)
            rec_stack.pop()

        for node in list(import_adj.keys()):
            if node not in visited:
                dfs(node)
        return findings
