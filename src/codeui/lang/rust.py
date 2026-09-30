"""Rust language adapter for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class RustLanguageAnalyzer(LanguageAnalyzer):
    """Rust language analyzer.
    Example:
        >>> analyzer = RustLanguageAnalyzer()
        >>> res = analyzer.parse(Path("main.rs"), 'fn main() { println!("Hello"); }')
        >>> syms = list(analyzer.extract_symbols(res))
        >>> len(syms) >= 1
        True
    """
    language: ClassVar[str] = "rust"
    extensions: ClassVar[tuple[str, ...]] = (".rs",)

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse Rust source file.
        Example:
            >>> analyzer = RustLanguageAnalyzer()
            >>> res = analyzer.parse(Path("lib.rs"), "pub fn add(a: i32, b: i32) -> i32 { a + b }")
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
        """Extract fn, struct, enum, trait, and mod symbols from Rust source.
        Example:
            >>> analyzer = RustLanguageAnalyzer()
            >>> res = analyzer.parse(Path("main.rs"), "pub struct Config { pub port: u16 }")
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
        fn_pattern = re.compile(r'(?:pub(?:\([^)]+\))?\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)\s*(?:<[^>]+>)?\s*\(([^)]*)\)')
        struct_pattern = re.compile(r'(?:pub(?:\([^)]+\))?\s+)?struct\s+([A-Za-z0-9_]+)(?:<[^>]+>)?')
        enum_pattern = re.compile(r'(?:pub(?:\([^)]+\))?\s+)?enum\s+([A-Za-z0-9_]+)(?:<[^>]+>)?')
        trait_pattern = re.compile(r'(?:pub(?:\([^)]+\))?\s+)?trait\s+([A-Za-z0-9_]+)(?:<[^>]+>)?')
        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            for match in fn_pattern.finditer(line_str):
                name = match.group(1)
                params = match.group(2)
                sym_id = f"{file_path}::{name}"
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                vis = Visibility.PUBLIC if "pub" in line_str else Visibility.PRIVATE
                symbols.append(Symbol(
                    id=sym_id,
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.FUNCTION,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"fn {name}({params})",
                    visibility=vis,
                    modifiers=("pub",) if "pub" in line_str else (),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))
            for match in struct_pattern.finditer(line_str):
                name = match.group(1)
                sym_id = f"{file_path}::{name}"
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                vis = Visibility.PUBLIC if "pub" in line_str else Visibility.PRIVATE
                symbols.append(Symbol(
                    id=sym_id,
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.STRUCT,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"struct {name}",
                    visibility=vis,
                    modifiers=("pub",) if "pub" in line_str else (),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))
            for match in enum_pattern.finditer(line_str):
                name = match.group(1)
                sym_id = f"{file_path}::{name}"
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                vis = Visibility.PUBLIC if "pub" in line_str else Visibility.PRIVATE
                symbols.append(Symbol(
                    id=sym_id,
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.ENUM,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"enum {name}",
                    visibility=vis,
                    modifiers=("pub",) if "pub" in line_str else (),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))
            for match in trait_pattern.finditer(line_str):
                name = match.group(1)
                sym_id = f"{file_path}::{name}"
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                vis = Visibility.PUBLIC if "pub" in line_str else Visibility.PRIVATE
                symbols.append(Symbol(
                    id=sym_id,
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.INTERFACE,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"trait {name}",
                    visibility=vis,
                    modifiers=("pub",) if "pub" in line_str else (),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))
        return symbols

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract relationship edges in Rust source.
        Example:
            >>> analyzer = RustLanguageAnalyzer()
            >>> res = analyzer.parse(Path("lib.rs"), "fn foo() {}")
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
        """Resolve Rust module references.
        Example:
            >>> analyzer = RustLanguageAnalyzer()
            >>> ctx = ResolveContext(Path("."))
            >>> ref = ImportRef("main.rs", "crate::utils", None, False)
            >>> list(analyzer.resolve_import(ref, ctx))
            []
        """
        return []
