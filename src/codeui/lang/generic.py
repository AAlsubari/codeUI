"""Generic markup, config, and fallback language analyzer for codeui."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class GenericLanguageAnalyzer(LanguageAnalyzer):
    """Fallback analyzer for configuration, markup, and generic source files.
    Example:
        >>> analyzer = GenericLanguageAnalyzer()
        >>> res = analyzer.parse(Path("config.json"), '{"key": "value"}')
        >>> syms = list(analyzer.extract_symbols(res))
        >>> len(syms) == 1
        True
    """
    language: ClassVar[str] = "generic"
    has_ast_support: ClassVar[bool] = False
    is_supported: ClassVar[bool] = False
    extensions: ClassVar[tuple[str, ...]] = (
        ".vue", ".svelte", ".m", ".mm", ".xml", ".html"
    )

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse source into generic result.
        Example:
            >>> analyzer = GenericLanguageAnalyzer()
            >>> res = analyzer.parse(Path("README.md"), "# Hello")
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
        """Extract top-level FILE symbol for generic documents.
        Example:
            >>> analyzer = GenericLanguageAnalyzer()
            >>> res = analyzer.parse(Path("a.txt"), "hello")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> syms[0].kind == SymbolKind.FILE
            True
        """
        file_path = parse.file_path
        lines = parse.source.splitlines()
        max_line = len(lines) if lines else 1
        return [
            Symbol(
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
        ]

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract edges for generic files (empty set).
        Example:
            >>> analyzer = GenericLanguageAnalyzer()
            >>> res = analyzer.parse(Path("a.txt"), "hello")
            >>> list(analyzer.extract_edges(res, []))
            []
        """
        return []

    def resolve_import(self, ref: ImportRef, ctx: ResolveContext) -> Iterable[str]:
        """Resolve import references for generic files.
        Example:
            >>> analyzer = GenericLanguageAnalyzer()
            >>> ctx = ResolveContext(Path("."))
            >>> ref = ImportRef("a.txt", "b", None, False)
            >>> list(analyzer.resolve_import(ref, ctx))
            []
        """
        return []
