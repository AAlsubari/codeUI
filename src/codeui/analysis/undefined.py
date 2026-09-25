"""Undefined symbol analyzer."""
import builtins
from pathlib import Path
from typing import ClassVar, Iterable, List, Set
from codeui.analysis.base import AnalysisContext, Analyzer
from codeui.core.graph import Graph
from codeui.core.ir import EdgeKind, Finding, Location, Severity

class UndefinedSymbolAnalyzer(Analyzer):
    """Detects references or calls to undefined symbols.
    Example:
        >>> analyzer = UndefinedSymbolAnalyzer()
        >>> g = Graph()
        >>> ctx = AnalysisContext(Path("."))
        >>> list(analyzer.run(g, ctx))
        []
    """
    id: ClassVar[str] = "undefined"
    severity_default: ClassVar[Severity] = Severity.ERROR

    PYTHON_BUILTINS = set(dir(builtins)) | {
        "Optional", "List", "Dict", "Set", "Tuple", "Any", "Callable", "Union",
        "Sequence", "Iterable", "Mapping", "Type", "ClassVar", "Literal", "Self",
        "dataclass", "field", "asdict", "Path", "Enum", "auto", "StrEnum",
    }

    JS_BUILTINS = {
        "console", "window", "document", "Math", "JSON", "Object", "Array", "String",
        "Number", "Boolean", "Symbol", "Map", "Set", "WeakMap", "WeakSet", "Proxy",
        "Reflect", "Promise", "Error", "TypeError", "RangeError", "SyntaxError",
        "encodeURIComponent", "decodeURIComponent", "encodeURI", "decodeURI",
        "fetch", "setTimeout", "clearTimeout", "setInterval", "clearInterval",
        "Element", "HTMLElement", "Event", "CustomEvent", "URLSearchParams",
        "FormData", "Headers", "Request", "Response", "Blob", "File", "FileReader",
        "localStorage", "sessionStorage", "location", "history", "globalThis",
        "process", "Buffer", "require", "exports", "module", "undefined", "NaN", "Infinity",
    }

    OTHER_BUILTINS = {
        "fmt", "make", "new", "println", "println!", "format!", "vec!", "panic!",
        "main", "self", "this", "super", "__name__", "__file__", "__doc__", "__all__"
    }

    BUILTINS = PYTHON_BUILTINS | JS_BUILTINS | OTHER_BUILTINS

    def run(self, graph: Graph, ctx: AnalysisContext) -> Iterable[Finding]:
        """Identify missing symbol references.
        Example:
            >>> analyzer = UndefinedSymbolAnalyzer()
            >>> g = Graph()
            >>> list(analyzer.run(g, AnalysisContext(Path("."))))
            []
        """
        findings: List[Finding] = []
        all_symbol_names = {s.name for s in graph.get_all_symbols()}
        all_symbol_names.update(self.BUILTINS)
        file_imports: dict[str, Set[str]] = {}
        for edge in graph.get_edges():
            if edge.kind == EdgeKind.IMPORTS:
                src_file = edge.source_id.split("::")[0]
                file_imports.setdefault(src_file, set())
                raw_mod = edge.target_id.replace("module::", "")
                imported = raw_mod.split(".")[-1]
                file_imports[src_file].add(imported)
                for part in raw_mod.split("."):
                    file_imports[src_file].add(part)

        for edge in graph.get_edges():
            if edge.kind in (EdgeKind.CALLS, EdgeKind.REFERENCES):
                target_id = edge.target_id
                if target_id.startswith("module::"):
                    continue
                target_name = target_id.split("::")[-1]
                src_file = edge.source_id.split("::")[0]

                if "." in target_name:
                    continue

                if (
                    not graph.has_symbol(target_id)
                    and target_name not in all_symbol_names
                    and target_name not in file_imports.get(src_file, set())
                    and not target_name.startswith("_")
                ):
                    loc = edge.location or Location(edge.source_id, 1, 0, 1, 0)
                    finding = Finding(
                        id=f"undefined::{target_id}",
                        rule_id="undefined_symbol",
                        message=f"Undefined symbol '{target_name}' referenced",
                        severity=self.severity_default,
                        location=loc,
                        symbol_id=edge.source_id,
                        fix_hint=f"Define symbol '{target_name}' or import it from module",
                        confidence=0.9,
                    )
                    findings.append(finding)
        return findings
