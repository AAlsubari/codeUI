"""C# language analyzer for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class CSharpLanguageAnalyzer(LanguageAnalyzer):
    """C# language analyzer.
    Example:
        >>> analyzer = CSharpLanguageAnalyzer()
        >>> res = analyzer.parse(Path("App.cs"), 'public class App { public void Run() {} }')
        >>> syms = list(analyzer.extract_symbols(res))
        >>> any(s.name == "App" for s in syms)
        True
    """
    language: ClassVar[str] = "csharp"
    extensions: ClassVar[tuple[str, ...]] = (".cs",)
    has_ast_support: ClassVar[bool] = True
    is_supported: ClassVar[bool] = True

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse C# source code into ParseResult.
        Example:
            >>> analyzer = CSharpLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.cs"), "using System;")
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
        """Extract namespaces, classes, interfaces, records, structs, and methods from C# source.
        Example:
            >>> analyzer = CSharpLanguageAnalyzer()
            >>> res = analyzer.parse(Path("User.cs"), "public class User { public string GetName() { return name; } }")
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

        using_pattern = re.compile(r'using\s+(?:static\s+)?([A-Za-z0-9_.]+)\s*;')
        class_pattern = re.compile(r'(?:public|protected|private|internal|file)?\s*(?:static|abstract|sealed|partial)?\s*(?:class|interface|record|struct)\s+([A-Za-z0-9_]+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?')
        method_pattern = re.compile(r'(?:public|protected|private|internal|static|async|override|virtual|abstract|partial|\s)+[\w<>\[\]?,.]+\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)')

        cs_keywords = {"if", "for", "while", "switch", "catch", "return", "throw", "new", "class", "interface", "namespace", "using", "else", "try", "finally"}
        class_ranges: List[tuple[str, str, int, int, str]] = []

        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("//") or line_str.startswith("*"):
                continue

            for match in using_pattern.finditer(line_str):
                using_path = match.group(1)
                sym_id = f"import:{using_path}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=using_path.split(".")[-1],
                    qualified_name=f"import:{using_path}",
                    kind=SymbolKind.IMPORT,
                    language=self.language,
                    location=Location(file_path, idx, line.find(using_path), idx, line.find(using_path) + len(using_path)),
                    parent_id=file_path,
                    signature=f"using {using_path}",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

            for match in class_pattern.finditer(line_str):
                cls_name = match.group(1)
                if cls_name in cs_keywords:
                    continue
                bases = match.group(2) or ""
                sym_id = f"{file_path}::{cls_name}"
                end_line = self._find_block_end(lines, idx - 1)
                class_ranges.append((cls_name, sym_id, idx, end_line, bases))
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
                if m_name in cs_keywords:
                    continue
                enclosing = next((c for c in reversed(class_ranges) if c[2] <= idx <= c[3]), None)
                if enclosing:
                    cls_name, cls_sym_id, _, _, _ = enclosing
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

        return symbols

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract relationship edges for C# AST.
        Example:
            >>> analyzer = CSharpLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.cs"), "using System.Text;")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        file_path = parse.file_path
        sym_map = {s.id: s for s in symbols}
        class_pattern = re.compile(r'(?:class|interface|record|struct)\s+([A-Za-z0-9_]+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?')
        call_pattern = re.compile(r'(?<![A-Za-z0-9_$-])\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
        cs_keywords = {"if", "for", "while", "switch", "catch", "return", "throw", "new", "typeof", "sizeof", "default"}

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
                bases_raw = match.group(2)
                if not bases_raw:
                    continue
                cls_sym_id = f"{file_path}::{cls_name}"
                for base_item in bases_raw.split(","):
                    base_clean = base_item.strip().split("<")[0].strip()
                    if not base_clean or base_clean in cs_keywords:
                        continue
                    is_iface = len(base_clean) > 1 and base_clean[0] == "I" and base_clean[1].isupper()
                    kind = EdgeKind.IMPLEMENTS if is_iface else EdgeKind.INHERITS
                    loc = Location(file_path, idx, line.find(base_clean), idx, line.find(base_clean) + len(base_clean))
                    edges.append(Edge(
                        source_id=cls_sym_id,
                        target_id=f"module::{base_clean}",
                        kind=kind,
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
                    if callee_name in cs_keywords or callee_name == m.name:
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
        """Resolve C# using references to project files.
        Example:
            >>> analyzer = CSharpLanguageAnalyzer()
            >>> ctx = ResolveContext(Path("."))
            >>> list(analyzer.resolve_import(ImportRef("App.cs", "System.Text", None, False), ctx))
            []
        """
        clean_path = ref.module_name.replace(".", "/")
        return ctx.resolve_path(ref.file_path, clean_path, self.language)
