"""C and C++ language analyzer for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class CppLanguageAnalyzer(LanguageAnalyzer):
    """C and C++ language analyzer.
    Example:
        >>> analyzer = CppLanguageAnalyzer()
        >>> res = analyzer.parse(Path("main.cpp"), '#include "helper.h"\\nint main() { return 0; }')
        >>> syms = list(analyzer.extract_symbols(res))
        >>> any(s.name == "main" for s in syms)
        True
    """
    language: ClassVar[str] = "cpp"
    extensions: ClassVar[tuple[str, ...]] = (".c", ".cpp", ".cc", ".cxx", ".h", ".hpp")
    has_ast_support: ClassVar[bool] = True
    is_supported: ClassVar[bool] = True

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse C or C++ source code into ParseResult.
        Example:
            >>> analyzer = CppLanguageAnalyzer()
            >>> res = analyzer.parse(Path("engine.cpp"), 'class Engine { public: void run(); };')
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
        """Extract functions, structs, classes, and include statements from C/C++ source.
        Example:
            >>> analyzer = CppLanguageAnalyzer()
            >>> res = analyzer.parse(Path("main.c"), 'void compute(int a) {}')
            >>> syms = list(analyzer.extract_symbols(res))
            >>> any(s.name == "compute" for s in syms)
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

        include_pattern = re.compile(r'#include\s+["<]([^">]+)[">]')
        class_pattern = re.compile(r'(?:class|struct)\s+([A-Za-z0-9_]+)(?:\s*:\s*(?:public|protected|private)?\s*([A-Za-z0-9_]+))?')
        func_pattern = re.compile(r'(?:[\w::<>*&]+\s+)+([A-Za-z0-9_]+)\s*\(([^)]*)\)\s*(?:const)?\s*[{;]')

        keywords = {"if", "for", "while", "switch", "catch", "return", "throw", "sizeof", "typedef", "struct", "class", "namespace"}
        class_ranges: List[tuple[str, str, int, int, str]] = []

        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("//") or line_str.startswith("/*") or line_str.startswith("*"):
                continue

            for match in include_pattern.finditer(line_str):
                inc = match.group(1)
                sym_id = f"import:{inc}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=inc,
                    qualified_name=f"import:{inc}",
                    kind=SymbolKind.IMPORT,
                    language=self.language,
                    location=Location(file_path, idx, line.find(inc), idx, line.find(inc) + len(inc)),
                    parent_id=file_path,
                    signature=f"#include <{inc}>",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

            for match in class_pattern.finditer(line_str):
                c_name = match.group(1)
                if c_name in keywords:
                    continue
                base_name = match.group(2) or ""
                sym_id = f"{file_path}::{c_name}"
                end_line = self._find_block_end(lines, idx - 1)
                class_ranges.append((c_name, sym_id, idx, end_line, base_name))
                loc = Location(file_path, idx, line.find(c_name), end_line, line.find(c_name) + len(c_name))
                symbols.append(Symbol(
                    id=sym_id,
                    name=c_name,
                    qualified_name=c_name,
                    kind=SymbolKind.CLASS,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"class {c_name}",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

            for match in func_pattern.finditer(line_str):
                f_name = match.group(1)
                params = match.group(2)
                if f_name in keywords:
                    continue
                enclosing = next((c for c in reversed(class_ranges) if c[2] <= idx <= c[3]), None)
                if enclosing:
                    cls_name, cls_sym_id, _, _, _ = enclosing
                    sym_id = f"{file_path}::{cls_name}::{f_name}"
                    qual_name = f"{cls_name}.{f_name}"
                    parent_sym_id = cls_sym_id
                    sym_kind = SymbolKind.METHOD
                else:
                    sym_id = f"{file_path}::{f_name}"
                    qual_name = f_name
                    parent_sym_id = file_path
                    sym_kind = SymbolKind.FUNCTION
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(f_name), end_line, line.find(f_name) + len(f_name))
                symbols.append(Symbol(
                    id=sym_id,
                    name=f_name,
                    qualified_name=qual_name,
                    kind=sym_kind,
                    language=self.language,
                    location=loc,
                    parent_id=parent_sym_id,
                    signature=f"{f_name}({params})",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

        return symbols

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract relationship edges for C/C++ AST.
        Example:
            >>> analyzer = CppLanguageAnalyzer()
            >>> res = analyzer.parse(Path("main.cpp"), '#include "helper.h"')
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        file_path = parse.file_path
        sym_map = {s.id: s for s in symbols}
        class_pattern = re.compile(r'(?:class|struct)\s+([A-Za-z0-9_]+)(?:\s*:\s*(?:public|protected|private)?\s*([A-Za-z0-9_]+))?')
        call_pattern = re.compile(r'(?<![A-Za-z0-9_$-])\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
        keywords = {"if", "for", "while", "switch", "catch", "return", "throw", "sizeof", "sizeof", "static_cast", "reinterpret_cast", "dynamic_cast"}

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
            if not line_str or line_str.startswith("//") or line_str.startswith("/*") or line_str.startswith("*"):
                continue
            for match in class_pattern.finditer(line_str):
                cls_name = match.group(1)
                base_name = match.group(2)
                if base_name and base_name not in keywords:
                    cls_sym_id = f"{file_path}::{cls_name}"
                    loc = Location(file_path, idx, line.find(base_name), idx, line.find(base_name) + len(base_name))
                    edges.append(Edge(
                        source_id=cls_sym_id,
                        target_id=f"module::{base_name}",
                        kind=EdgeKind.INHERITS,
                        weight=1.0,
                        confidence=0.9,
                        location=loc,
                    ))

        func_syms = [s for s in symbols if s.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD)]
        name_to_syms: dict[str, list[Symbol]] = {}
        for s in func_syms:
            name_to_syms.setdefault(s.name, []).append(s)

        for f in func_syms:
            if not f.location:
                continue
            f_lines = lines[f.location.start_line - 1 : f.location.end_line]
            for f_line in f_lines:
                for match in call_pattern.finditer(f_line):
                    callee_name = match.group(1)
                    if callee_name in keywords or callee_name == f.name:
                        continue
                    if callee_name in name_to_syms:
                        target = name_to_syms[callee_name][0]
                        edges.append(Edge(
                            source_id=f.id,
                            target_id=target.id,
                            kind=EdgeKind.CALLS,
                            weight=1.0,
                            confidence=0.85,
                            location=f.location,
                        ))

        return edges

    def resolve_import(self, ref: ImportRef, ctx: ResolveContext) -> Iterable[str]:
        """Resolve C/C++ include references to project header files.
        Example:
            >>> analyzer = CppLanguageAnalyzer()
            >>> ctx = ResolveContext(Path("."))
            >>> list(analyzer.resolve_import(ImportRef("main.cpp", "helper.h", None, False), ctx))
            []
        """
        return ctx.resolve_path(ref.file_path, ref.module_name, self.language)

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
