"""Java and Kotlin language analyzer for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class JavaLanguageAnalyzer(LanguageAnalyzer):
    """Java and Kotlin language analyzer.
    Example:
        >>> analyzer = JavaLanguageAnalyzer()
        >>> res = analyzer.parse(Path("Main.java"), 'public class Main { public static void main(String[] args) {} }')
        >>> syms = list(analyzer.extract_symbols(res))
        >>> any(s.name == "Main" for s in syms)
        True
    """
    language: ClassVar[str] = "java"
    extensions: ClassVar[tuple[str, ...]] = (".java", ".kt")
    has_ast_support: ClassVar[bool] = True
    is_supported: ClassVar[bool] = True

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse Java or Kotlin source code into ParseResult.
        Example:
            >>> analyzer = JavaLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.java"), "package com.example;")
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
        """Extract classes, interfaces, records, enums, and methods from Java/Kotlin source.
        Example:
            >>> analyzer = JavaLanguageAnalyzer()
            >>> res = analyzer.parse(Path("User.java"), "public class User { public String getName() { return name; } }")
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

        import_pattern = re.compile(r'import\s+(?:static\s+)?([A-Za-z0-9_.*]+)\s*;')
        class_pattern = re.compile(r'(?:public|protected|private)?\s*(?:abstract|final|static)?\s*(?:class|interface|record|enum)\s+([A-Za-z0-9_]+)(?:<[^>]+>)?(?:\s+extends\s+([A-Za-z0-9_$.]+))?(?:\s+implements\s+([A-Za-z0-9_$,\s]+))?')
        method_pattern = re.compile(r'(?:public|protected|private|static|final|synchronized|abstract|\s)+[\w<>\[\]]+\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)')
        kt_fun_pattern = re.compile(r'(?:public|private|protected|internal)?\s*fun\s+(?:<[^>]+>\s+)?([A-Za-z0-9_]+)\s*\(([^)]*)\)')

        js_keywords = {"if", "for", "while", "switch", "catch", "return", "throw", "new", "class", "interface", "package", "import", "else", "try", "finally"}
        class_ranges: List[tuple[str, str, int, int, str, str]] = []

        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("//") or line_str.startswith("*"):
                continue

            for match in import_pattern.finditer(line_str):
                imp_path = match.group(1)
                sym_id = f"import:{imp_path}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=imp_path.split(".")[-1],
                    qualified_name=f"import:{imp_path}",
                    kind=SymbolKind.IMPORT,
                    language=self.language,
                    location=Location(file_path, idx, line.find(imp_path), idx, line.find(imp_path) + len(imp_path)),
                    parent_id=file_path,
                    signature=f"import {imp_path}",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

            for match in class_pattern.finditer(line_str):
                cls_name = match.group(1)
                if cls_name in js_keywords:
                    continue
                ext_name = match.group(2) or ""
                impl_names = match.group(3) or ""
                sym_id = f"{file_path}::{cls_name}"
                end_line = self._find_block_end(lines, idx - 1)
                class_ranges.append((cls_name, sym_id, idx, end_line, ext_name, impl_names))
                loc = Location(file_path, idx, line.find(cls_name), end_line, line.find(cls_name) + len(cls_name))
                vis = Visibility.PUBLIC if "public" in line_str else (Visibility.PRIVATE if "private" in line_str else Visibility.INTERNAL)
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
                    modifiers=("public",) if "public" in line_str else (),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

            for match in method_pattern.finditer(line_str):
                m_name = match.group(1)
                params = match.group(2)
                if m_name in js_keywords or m_name in ("if", "for", "while", "switch", "catch", "return"):
                    continue
                enclosing = next((c for c in reversed(class_ranges) if c[2] <= idx <= c[3]), None)
                if enclosing:
                    cls_name, cls_sym_id, _, _, _, _ = enclosing
                    sym_id = f"{file_path}::{cls_name}::{m_name}"
                    qual_name = f"{cls_name}.{m_name}"
                    parent_sym_id = cls_sym_id
                else:
                    sym_id = f"{file_path}::{m_name}"
                    qual_name = m_name
                    parent_sym_id = file_path
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(m_name), end_line, line.find(m_name) + len(m_name))
                vis = Visibility.PUBLIC if "public" in line_str else (Visibility.PRIVATE if "private" in line_str else Visibility.INTERNAL)
                symbols.append(Symbol(
                    id=sym_id,
                    name=m_name,
                    qualified_name=qual_name,
                    kind=SymbolKind.METHOD,
                    language=self.language,
                    location=loc,
                    parent_id=parent_sym_id,
                    signature=f"{m_name}({params})",
                    visibility=vis,
                    modifiers=("public",) if "public" in line_str else (),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

            for match in kt_fun_pattern.finditer(line_str):
                m_name = match.group(1)
                params = match.group(2)
                if m_name in js_keywords:
                    continue
                enclosing = next((c for c in reversed(class_ranges) if c[2] <= idx <= c[3]), None)
                if enclosing:
                    cls_name, cls_sym_id, _, _, _, _ = enclosing
                    sym_id = f"{file_path}::{cls_name}::{m_name}"
                    qual_name = f"{cls_name}.{m_name}"
                    parent_sym_id = cls_sym_id
                else:
                    sym_id = f"{file_path}::{m_name}"
                    qual_name = m_name
                    parent_sym_id = file_path
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(m_name), end_line, line.find(m_name) + len(m_name))
                symbols.append(Symbol(
                    id=sym_id,
                    name=m_name,
                    qualified_name=qual_name,
                    kind=SymbolKind.FUNCTION,
                    language=self.language,
                    location=loc,
                    parent_id=parent_sym_id,
                    signature=f"fun {m_name}({params})",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

        return symbols

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract relationship edges for Java / Kotlin AST.
        Example:
            >>> analyzer = JavaLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.java"), "import com.example.Helper;")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        file_path = parse.file_path
        sym_map = {s.id: s for s in symbols}
        class_pattern = re.compile(r'(?:class|interface|record|enum)\s+([A-Za-z0-9_]+)(?:<[^>]+>)?(?:\s+extends\s+([A-Za-z0-9_$.]+))?(?:\s+implements\s+([A-Za-z0-9_$,\s]+))?')
        call_pattern = re.compile(r'(?<![A-Za-z0-9_$-])\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
        java_keywords = {"if", "for", "while", "switch", "catch", "return", "throw", "new", "super", "this"}

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
                target_mod = s.qualified_name.replace("import:", "")
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
            if not line_str or line_str.startswith("//") or line_str.startswith("*"):
                continue
            for match in class_pattern.finditer(line_str):
                cls_name = match.group(1)
                ext_name = match.group(2)
                impl_names = match.group(3)
                cls_sym_id = f"{file_path}::{cls_name}"
                if ext_name:
                    base_clean = ext_name.strip().split("<")[0].strip()
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
                        iface_clean = iface.strip().split("<")[0].strip()
                        if iface_clean and iface_clean not in java_keywords:
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
                    if callee_name in java_keywords or callee_name == m.name:
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
        """Resolve Java import references to project files.
        Example:
            >>> analyzer = JavaLanguageAnalyzer()
            >>> ctx = ResolveContext(Path("."))
            >>> list(analyzer.resolve_import(ImportRef("App.java", "com.example.Helper", None, False), ctx))
            []
        """
        clean_path = ref.module_name.replace(".", "/")
        return ctx.resolve_path(ref.file_path, clean_path, self.language)

    def _find_block_end(self, lines: List[str], start_idx: int) -> int:
        open_braces = 0
        found_brace = False
        for i in range(start_idx, len(lines)):
            line = lines[i]
            open_braces += line.count("{") - line.count("}")
            if "{" in line:
                found_brace = True
            if found_brace and open_braces <= 0:
                return i + 1
        return min(start_idx + 30, len(lines))

    def _extract_body_hash(self, lines: List[str], start_idx: int) -> str:
        end_idx = self._find_block_end(lines, start_idx)
        snippet = "\n".join(lines[start_idx:end_idx])
        return hashlib.sha256(snippet.encode("utf-8")).hexdigest()
