"""PHP language analyzer for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class PHPLanguageAnalyzer(LanguageAnalyzer):
    """PHP language analyzer.
    Example:
        >>> analyzer = PHPLanguageAnalyzer()
        >>> res = analyzer.parse(Path("App.php"), '<?php namespace App; class Controller { public function index() {} }')
        >>> syms = list(analyzer.extract_symbols(res))
        >>> any(s.name == "Controller" for s in syms)
        True
    """
    language: ClassVar[str] = "php"
    extensions: ClassVar[tuple[str, ...]] = (".php",)
    has_ast_support: ClassVar[bool] = True
    is_supported: ClassVar[bool] = True

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse PHP source code into ParseResult.
        Example:
            >>> analyzer = PHPLanguageAnalyzer()
            >>> res = analyzer.parse(Path("User.php"), "<?php namespace App\Models;")
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
        """Extract namespaces, classes, interfaces, traits, enums, functions, and methods from PHP source.
        Example:
            >>> analyzer = PHPLanguageAnalyzer()
            >>> res = analyzer.parse(Path("Post.php"), "<?php class Post { public function save() {} }")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> len(syms) >= 2
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

        use_pattern = re.compile(r'use\s+([A-Za-z0-9_\\]+)(?:\s+as\s+([A-Za-z0-9_]+))?\s*;')
        class_pattern = re.compile(r'(?:abstract|final|readonly)?\s*(?:class|interface|trait|enum)\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_\\]+))?(?:\s+implements\s+([A-Za-z0-9_\\,\s]+))?')
        method_pattern = re.compile(r'(?:public|protected|private|static|final|abstract|\s)+function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)')
        func_pattern = re.compile(r'function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)')

        php_keywords = {"if", "for", "while", "switch", "catch", "return", "throw", "new", "class", "interface", "namespace", "use", "else", "try", "finally", "echo", "print"}
        class_ranges: List[tuple[str, str, int, int, str, str]] = []

        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("//") or line_str.startswith("#") or line_str.startswith("*"):
                continue

            for match in use_pattern.finditer(line_str):
                use_path = match.group(1)
                alias = match.group(2) or use_path.split("\\")[-1]
                sym_id = f"import:{use_path}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=alias,
                    qualified_name=f"import:{use_path}",
                    kind=SymbolKind.IMPORT,
                    language=self.language,
                    location=Location(file_path, idx, line.find(use_path), idx, line.find(use_path) + len(use_path)),
                    parent_id=file_path,
                    signature=f"use {use_path}",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

            for match in class_pattern.finditer(line_str):
                cls_name = match.group(1)
                if cls_name in php_keywords:
                    continue
                ext_name = match.group(2) or ""
                impl_names = match.group(3) or ""
                sym_id = f"{file_path}::{cls_name}"
                end_line = self._find_block_end(lines, idx - 1)
                class_ranges.append((cls_name, sym_id, idx, end_line, ext_name, impl_names))
                loc = Location(file_path, idx, line.find(cls_name), end_line, line.find(cls_name) + len(cls_name))
                vis = Visibility.PUBLIC if "public" in line_str or "abstract" in line_str or "final" in line_str else Visibility.INTERNAL
                symbols.append(Symbol(
                    id=sym_id,
                    name=cls_name,
                    qualified_name=cls_name,
                    kind=SymbolKind.CLASS,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"class {cls_name}",
                    visibility=vis,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

            for match in method_pattern.finditer(line_str):
                m_name = match.group(1)
                params = match.group(2)
                if m_name in php_keywords:
                    continue
                enclosing = next((c for c in reversed(class_ranges) if c[2] <= idx <= c[3]), None)
                if enclosing:
                    cls_name, cls_sym_id, _, _, _, _ = enclosing
                    sym_id = f"{file_path}::{cls_name}::{m_name}"
                    qual_name = f"{cls_name}::{m_name}"
                    parent_sym_id = cls_sym_id
                    sym_kind = SymbolKind.METHOD
                else:
                    sym_id = f"{file_path}::{m_name}"
                    qual_name = m_name
                    parent_sym_id = file_path
                    sym_kind = SymbolKind.FUNCTION
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(m_name), end_line, line.find(m_name) + len(m_name))
                vis = Visibility.PRIVATE if "private" in line_str else (Visibility.PROTECTED if "protected" in line_str else Visibility.PUBLIC)
                symbols.append(Symbol(
                    id=sym_id,
                    name=m_name,
                    qualified_name=qual_name,
                    kind=sym_kind,
                    language=self.language,
                    location=loc,
                    parent_id=parent_sym_id,
                    signature=f"function {m_name}({params})",
                    visibility=vis,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

        return symbols

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract relationship edges for PHP AST.
        Example:
            >>> analyzer = PHPLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.php"), "<?php use App\\Helper;")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        file_path = parse.file_path
        sym_map = {s.id: s for s in symbols}
        class_pattern = re.compile(r'(?:class|interface|trait|enum)\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_\\]+))?(?:\s+implements\s+([A-Za-z0-9_\\,\s]+))?')
        call_pattern = re.compile(r'(?<![A-Za-z0-9_$-])\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
        php_keywords = {"if", "for", "while", "switch", "catch", "return", "throw", "new", "echo", "print", "isset", "empty", "unset"}

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
            if s.kind == SymbolKind.IMPORT:
                target_mod = s.qualified_name.replace("import:", "").replace("\\", "/")
                edges.append(Edge(
                    source_id=file_path,
                    target_id=f"module::{target_mod}",
                    kind=EdgeKind.IMPORTS,
                    weight=1.0,
                    confidence=1.0,
                    location=s.location,
                ))

        lines = parse.source.splitlines()
        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("//") or line_str.startswith("#") or line_str.startswith("*"):
                continue
            for match in class_pattern.finditer(line_str):
                cls_name = match.group(1)
                ext_name = match.group(2)
                impl_names = match.group(3)
                cls_sym_id = f"{file_path}::{cls_name}"
                if ext_name:
                    base_clean = ext_name.split("\\")[-1]
                    loc = Location(file_path, idx, line.find(base_clean), idx, line.find(base_clean) + len(base_clean))
                    edges.append(Edge(
                        source_id=cls_sym_id,
                        target_id=f"module::{base_clean}",
                        kind=EdgeKind.INHERITS,
                        weight=1.0,
                        confidence=0.9,
                        location=loc,
                    ))
                if impl_names:
                    for iface in impl_names.split(","):
                        iface_clean = iface.strip().split("\\")[-1]
                        if iface_clean and iface_clean not in php_keywords:
                            loc = Location(file_path, idx, line.find(iface_clean), idx, line.find(iface_clean) + len(iface_clean))
                            edges.append(Edge(
                                source_id=cls_sym_id,
                                target_id=f"module::{iface_clean}",
                                kind=EdgeKind.IMPLEMENTS,
                                weight=1.0,
                                confidence=0.9,
                                location=loc,
                            ))

        method_syms = [s for s in symbols if s.kind in (SymbolKind.METHOD, SymbolKind.FUNCTION)]
        name_to_syms: dict[str, list[Symbol]] = {}
        for s in method_syms:
            name_to_syms.setdefault(s.name, []).append(s)

        for m in method_syms:
            if not m.location:
                continue
            m_lines = lines[m.location.start_line - 1 : m.location.end_line]
            for m_line in m_lines:
                for match in call_pattern.finditer(m_line):
                    callee_name = match.group(1)
                    if callee_name in php_keywords or callee_name == m.name:
                        continue
                    if callee_name in name_to_syms:
                        target = name_to_syms[callee_name][0]
                        edges.append(Edge(
                            source_id=m.id,
                            target_id=target.id,
                            kind=EdgeKind.CALLS,
                            weight=1.0,
                            confidence=0.85,
                            location=m.location,
                        ))

        return edges

    def resolve_import(self, ref: ImportRef, ctx: ResolveContext) -> Iterable[str]:
        """Resolve PHP use references to project files.
        Example:
            >>> analyzer = PHPLanguageAnalyzer()
            >>> ctx = ResolveContext(Path("."))
            >>> list(analyzer.resolve_import(ImportRef("App.php", "App\\Helper", None, False), ctx))
            []
        """
        clean_path = ref.module_name.replace("\\", "/")
        return ctx.resolve_path(ref.file_path, clean_path, self.language)
