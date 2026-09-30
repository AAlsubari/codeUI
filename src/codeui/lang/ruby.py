"""Ruby language analyzer for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class RubyLanguageAnalyzer(LanguageAnalyzer):
    """Ruby language analyzer.
    Example:
        >>> analyzer = RubyLanguageAnalyzer()
        >>> res = analyzer.parse(Path("app.rb"), 'class App < Base\\n  def run\\n  end\\nend')
        >>> syms = list(analyzer.extract_symbols(res))
        >>> any(s.name == "App" for s in syms)
        True
    """
    language: ClassVar[str] = "ruby"
    extensions: ClassVar[tuple[str, ...]] = (".rb",)
    has_ast_support: ClassVar[bool] = True
    is_supported: ClassVar[bool] = True

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse Ruby source code into ParseResult.
        Example:
            >>> analyzer = RubyLanguageAnalyzer()
            >>> res = analyzer.parse(Path("main.rb"), "require 'json'")
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
        """Extract modules, classes, and methods from Ruby source.
        Example:
            >>> analyzer = RubyLanguageAnalyzer()
            >>> res = analyzer.parse(Path("user.rb"), "class User\\n  def name\\n  end\\nend")
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

        require_pattern = re.compile(r'require(?:_relative)?\s+["\']([^"\']+)["\']')
        class_pattern = re.compile(r'(?:class|module)\s+([A-Za-z0-9_:]+)(?:\s*<\s*([A-Za-z0-9_:]+))?')
        def_pattern = re.compile(r'def\s+(?:self\.)?([A-Za-z0-9_?!]+)(?:\s*\(([^)]*)\))?')

        ruby_keywords = {"if", "for", "while", "unless", "until", "case", "when", "then", "begin", "rescue", "ensure", "end", "return", "class", "module", "def"}
        class_ranges: List[tuple[str, str, int, int, str]] = []

        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            for match in require_pattern.finditer(line_str):
                req_path = match.group(1)
                sym_id = f"import:{req_path}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=req_path.split("/")[-1],
                    qualified_name=f"import:{req_path}",
                    kind=SymbolKind.IMPORT,
                    language=self.language,
                    location=Location(file_path, idx, line.find(req_path), idx, line.find(req_path) + len(req_path)),
                    parent_id=file_path,
                    signature=f"require '{req_path}'",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

            for match in class_pattern.finditer(line_str):
                cls_name = match.group(1)
                if cls_name in ruby_keywords:
                    continue
                base_name = match.group(2) or ""
                sym_id = f"{file_path}::{cls_name}"
                end_line = self._find_ruby_block_end(lines, idx - 1)
                class_ranges.append((cls_name, sym_id, idx, end_line, base_name))
                loc = Location(file_path, idx, line.find(cls_name), end_line, line.find(cls_name) + len(cls_name))
                symbols.append(Symbol(
                    id=sym_id,
                    name=cls_name,
                    qualified_name=cls_name,
                    kind=SymbolKind.CLASS,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"class {cls_name}",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

            for match in def_pattern.finditer(line_str):
                m_name = match.group(1)
                params = match.group(2) or ""
                if m_name in ruby_keywords:
                    continue
                enclosing = next((c for c in reversed(class_ranges) if c[2] <= idx <= c[3]), None)
                if enclosing:
                    cls_name, cls_sym_id, _, _, _ = enclosing
                    sym_id = f"{file_path}::{cls_name}::{m_name}"
                    qual_name = f"{cls_name}#{m_name}"
                    parent_sym_id = cls_sym_id
                    sym_kind = SymbolKind.METHOD
                else:
                    sym_id = f"{file_path}::{m_name}"
                    qual_name = m_name
                    parent_sym_id = file_path
                    sym_kind = SymbolKind.FUNCTION
                end_line = self._find_ruby_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(m_name), end_line, line.find(m_name) + len(m_name))
                symbols.append(Symbol(
                    id=sym_id,
                    name=m_name,
                    qualified_name=qual_name,
                    kind=sym_kind,
                    language=self.language,
                    location=loc,
                    parent_id=parent_sym_id,
                    signature=f"def {m_name}({params})",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))

        return symbols

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract relationship edges for Ruby AST.
        Example:
            >>> analyzer = RubyLanguageAnalyzer()
            >>> res = analyzer.parse(Path("app.rb"), "require 'helper'")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        file_path = parse.file_path
        sym_map = {s.id: s for s in symbols}
        class_pattern = re.compile(r'class\s+([A-Za-z0-9_:]+)(?:\s*<\s*([A-Za-z0-9_:]+))?')
        call_pattern = re.compile(r'(?<![A-Za-z0-9_$-])\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|\s+[A-Za-z0-9_:"\'])')
        ruby_keywords = {"if", "for", "while", "unless", "until", "case", "when", "then", "begin", "rescue", "ensure", "end", "return", "class", "module", "def", "puts", "print"}

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
            if not line_str or line_str.startswith("#"):
                continue
            for match in class_pattern.finditer(line_str):
                cls_name = match.group(1)
                base_name = match.group(2)
                if base_name and base_name not in ruby_keywords:
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
                    if callee_name in ruby_keywords or callee_name == f.name:
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
        """Resolve Ruby require references to project files.
        Example:
            >>> analyzer = RubyLanguageAnalyzer()
            >>> ctx = ResolveContext(Path("."))
            >>> list(analyzer.resolve_import(ImportRef("app.rb", "helper", None, False), ctx))
            []
        """
        clean_path = ref.module_name.replace(".", "/")
        return ctx.resolve_path(ref.file_path, clean_path, self.language)

    def _find_ruby_block_end(self, lines: List[str], start_idx: int) -> int:
        nesting = 0
        block_starters = ("def ", "class ", "module ", "if ", "unless ", "case ", "while ", "until ", "for ", "begin ", "do ")
        for i in range(start_idx, len(lines)):
            l = lines[i].strip()
            if not l or l.startswith("#"):
                continue
            if any(l.startswith(bs) for bs in block_starters) or l == "do":
                nesting += 1
            if l == "end" or l.startswith("end ") or l.endswith(" end"):
                nesting -= 1
                if nesting <= 0:
                    return i + 1
        return min(start_idx + 30, len(lines))
