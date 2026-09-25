"""Base interface for language AST adapters."""
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Iterable, List, Sequence
from codeui.core.ir import Edge, Location, Symbol
from codeui.core.resolver import ResolveContext

@dataclass
class ParseResult:
    """Encapsulates parse AST result and errors.
    Example:
        >>> res = ParseResult("app.py", "x = 1", None, "hash1", [])
        >>> res.file_path
        'app.py'
    """
    file_path: str
    source: str
    ast: Any
    content_hash: str
    errors: List[str]

@dataclass
class ImportRef:
    """Import reference descriptor.
    Example:
        >>> ref = ImportRef("app.py", "math", None, False)
        >>> ref.module_name
        'math'
    """
    file_path: str
    module_name: str
    symbol_name: str | None
    is_relative: bool

class LanguageAnalyzer(ABC):
    """Abstract base class for language analyzers.
    Example:
        >>> class MockLang(LanguageAnalyzer):
        ...     language = "mock"
        ...     extensions = (".mock",)
        ...     def parse(self, path, source): return ParseResult(str(path), source, None, "h", [])
        ...     def extract_symbols(self, parse): return []
        ...     def extract_edges(self, parse, symbols): return []
        ...     def resolve_import(self, ref, ctx): return []
        >>> mock = MockLang()
        >>> mock.language
        'mock'
    """
    language: ClassVar[str]
    extensions: ClassVar[tuple[str, ...]]
    has_ast_support: ClassVar[bool] = True
    is_supported: ClassVar[bool] = True

    @abstractmethod
    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse source code into AST payload."""
        pass

    @abstractmethod
    def extract_symbols(self, parse: ParseResult) -> Iterable[Symbol]:
        """Extract symbol hierarchy from parse result."""
        pass

    @abstractmethod
    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract relationship edges between symbols."""
        pass

    @abstractmethod
    def resolve_import(self, ref: ImportRef, ctx: ResolveContext) -> Iterable[str]:
        """Resolve import reference to candidate project files."""
        pass

    def _extract_body_hash(self, lines: Sequence[str], start_idx: int) -> str:
        """Extract a deterministic hash of code body starting at start_idx."""
        snippet_lines = []
        brace_count = 0
        found_open = False
        for i in range(start_idx, min(len(lines), start_idx + 80)):
            l = lines[i]
            snippet_lines.append(l)
            brace_count += l.count("{") - l.count("}")
            if "{" in l:
                found_open = True
            if found_open and brace_count <= 0:
                break
        body = "\n".join(snippet_lines).strip()
        if not body and start_idx < len(lines):
            body = lines[start_idx].strip()
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]

    def _find_block_end(self, lines: Sequence[str], start_idx: int) -> int:
        """Find the 1-based end line of a block starting at 0-based start_idx.
        Example:
            >>> class MockLang(LanguageAnalyzer):
            ...     language = "mock"
            ...     extensions = ()
            ...     def parse(self, p, s): pass
            ...     def extract_symbols(self, p): pass
            ...     def extract_edges(self, p, s): pass
            ...     def resolve_import(self, r, c): pass
            >>> m = MockLang()
            >>> m._find_block_end(["func foo() {", "  return 1", "}"], 0)
            3
        """
        brace_count = 0
        found_open = False
        for i in range(start_idx, len(lines)):
            l = lines[i]
            brace_count += l.count("{") - l.count("}")
            if "{" in l:
                found_open = True
            if found_open and brace_count <= 0:
                return i + 1
        return min(len(lines), start_idx + 1)
