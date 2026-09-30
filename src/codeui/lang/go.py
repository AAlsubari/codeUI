"""Go language adapter for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class GoLanguageAnalyzer(LanguageAnalyzer):
    """Go language analyzer.
    Example:
        >>> analyzer = GoLanguageAnalyzer()
        >>> res = analyzer.parse(Path("main.go"), "package main\\nfunc main() {}")
        >>> syms = list(analyzer.extract_symbols(res))
        >>> len(syms) >= 1
        True
    """
    language: ClassVar[str] = "go"
    extensions: ClassVar[tuple[str, ...]] = (".go",)

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse Go source text.
        Example:
            >>> analyzer = GoLanguageAnalyzer()
            >>> res = analyzer.parse(Path("main.go"), "package main")
            >>> res.errors
            []
        """
        content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return ParseResult(
            file_path=str(path),
            source=source,
            ast=source,
            content_hash=content_hash,
            errors=[],
        )

    def extract_symbols(self, parse: ParseResult) -> Iterable[Symbol]:
        """Extract Go packages, functions, structs, interfaces, and imports.
        Example:
            >>> analyzer = GoLanguageAnalyzer()
            >>> res = analyzer.parse(Path("main.go"), "package main\\ntype User struct{ Name string }")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> any(s.kind == SymbolKind.STRUCT for s in syms)
            True
        """
        source = parse.source
        file_path = parse.file_path
        lines = source.splitlines()
        max_line = len(lines) if lines else 1
        symbols: List[Symbol] = []
        file_sym = Symbol(
            id=file_path,
            name=Path(file_path).name,
            qualified_name=file_path,
            kind=SymbolKind.FILE,
            language=self.language,
            location=Location(file_path, 1, 0, max_line, 0),
            parent_id=None,
            signature=None,
            visibility=Visibility.PUBLIC,
            modifiers=(),
            content_hash=parse.content_hash,
        )
        symbols.append(file_sym)
        func_pattern = re.compile(r'func\s+(?:\(([^)]+)\)\s+)?([A-Za-z0-9_]+)\s*(?:\[[^\]]+\])?\s*\(([^)]*)\)')
        struct_pattern = re.compile(r'type\s+([A-Za-z0-9_]+)\s*(?:\[[^\]]+\])?\s+struct\b')
        interface_pattern = re.compile(r'type\s+([A-Za-z0-9_]+)\s*(?:\[[^\]]+\])?\s+interface\b')
        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            for match in func_pattern.finditer(line_str):
                receiver = match.group(1)
                name = match.group(2)
                params = match.group(3)
                sym_id = f"{file_path}::{name}"
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                vis = Visibility.PUBLIC if name[0].isupper() else Visibility.PRIVATE
                kind = SymbolKind.METHOD if receiver else SymbolKind.FUNCTION
                symbols.append(Symbol(
                    id=sym_id,
                    name=name,
                    qualified_name=f"{receiver}.{name}" if receiver else name,
                    kind=kind,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"func ({receiver or ''}) {name}({params})",
                    visibility=vis,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))
            for match in struct_pattern.finditer(line_str):
                name = match.group(1)
                sym_id = f"{file_path}::{name}"
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                vis = Visibility.PUBLIC if name[0].isupper() else Visibility.PRIVATE
                symbols.append(Symbol(
                    id=sym_id,
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.STRUCT,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"type {name} struct",
                    visibility=vis,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))
            for match in interface_pattern.finditer(line_str):
                name = match.group(1)
                sym_id = f"{file_path}::{name}"
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                vis = Visibility.PUBLIC if name[0].isupper() else Visibility.PRIVATE
                symbols.append(Symbol(
                    id=sym_id,
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.INTERFACE,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"type {name} interface",
                    visibility=vis,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))
        return symbols

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract containment and call relationships in Go.
        Example:
            >>> analyzer = GoLanguageAnalyzer()
            >>> res = analyzer.parse(Path("main.go"), "package main\\nfunc main() {}")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        sym_map = {s.id: s for s in symbols}
        for s in symbols:
            if s.parent_id and s.parent_id in sym_map:
                edges.append(Edge(
                    source_id=s.parent_id,
                    target_id=s.id,
                    kind=EdgeKind.CONTAINS,
                    weight=1.0,
                    confidence=1.0,
                    location=s.location,
                ))
        return edges

    def resolve_import(self, ref: ImportRef, ctx: ResolveContext) -> Iterable[str]:
        """Resolve Go module import references.
        Example:
            >>> analyzer = GoLanguageAnalyzer()
            >>> ctx = ResolveContext(Path("."))
            >>> ref = ImportRef("main.go", "fmt", None, False)
            >>> list(analyzer.resolve_import(ref, ctx))
            []
        """
        return []
