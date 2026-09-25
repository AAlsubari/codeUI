"""Duplicate code analyzer using structure token shingling."""
import hashlib
from pathlib import Path
from typing import ClassVar, Dict, Iterable, List, Set, Tuple
from codeui.analysis.base import AnalysisContext, Analyzer
from codeui.core.graph import Graph
from codeui.core.ir import EdgeKind, Finding, Location, Severity, SymbolKind

class DuplicateCodeAnalyzer(Analyzer):
    """Detects near-duplicate symbol bodies using structure token shingle hashing.
    Example:
        >>> analyzer = DuplicateCodeAnalyzer()
        >>> g = Graph()
        >>> ctx = AnalysisContext(Path("."))
        >>> list(analyzer.run(g, ctx))
        []
    """
    id: ClassVar[str] = "duplicates"
    severity_default: ClassVar[Severity] = Severity.WARNING

    BOILERPLATE_NAMES = {
        "__init__", "__repr__", "__str__", "__post_init__", "__eq__", "__hash__",
        "to_dict", "to_json", "from_dict", "from_json", "run", "parse", "get", "set",
        "close", "open", "read", "write", "validate", "setup", "teardown", "main",
        "render", "update", "handle", "onClick", "onChange", "execute", "cleanup",
        "dispose", "destroy", "build", "create", "clone", "reset", "refresh",
        "render_ui", "get_state", "set_state", "getId", "getName", "process"
    }

    def run(self, graph: Graph, ctx: AnalysisContext) -> Iterable[Finding]:
        """Identify duplicate symbol bodies.
        Example:
            >>> analyzer = DuplicateCodeAnalyzer()
            >>> g = Graph()
            >>> list(analyzer.run(g, AnalysisContext(Path("."))))
            []
        """
        findings: List[Finding] = []
        hash_to_symbols: Dict[str, List[Tuple[str, str, Location]]] = {}
        for sym in graph.get_all_symbols():
            if sym.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD) and sym.content_hash:
                if sym.name in self.BOILERPLATE_NAMES or sym.name.startswith("__") or sym.name.startswith("test_"):
                    continue
                if sym.location and sym.location.end_line and (sym.location.end_line - sym.location.start_line < 3):
                    continue
                hash_to_symbols.setdefault(sym.content_hash, []).append((sym.id, sym.name, sym.location))

        for content_hash, sym_list in hash_to_symbols.items():
            if len(sym_list) > 1:
                first_id, first_name, first_loc = sym_list[0]
                first_file = first_id.split("::")[0]
                for dup_id, dup_name, dup_loc in sym_list[1:]:
                    dup_file = dup_id.split("::")[0]
                    if first_id == dup_id:
                        continue
                    if first_file == dup_file and first_name == dup_name:
                        continue
                    finding = Finding(
                        id=f"duplicates::{first_id}::{dup_id}",
                        rule_id="duplicate_code",
                        message=f"Duplicate symbol implementation found between '{first_name}' and '{dup_name}'",
                        severity=self.severity_default,
                        location=dup_loc,
                        symbol_id=dup_id,
                        fix_hint=f"Extract duplicate logic from '{dup_name}' into a shared helper function",
                        confidence=0.85,
                    )
                    findings.append(finding)
        return findings
