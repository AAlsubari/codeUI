"""Dart language adapter for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class DartLanguageAnalyzer(LanguageAnalyzer):
    """Dart language adapter extracting classes, mixins, enums, functions, and properties.
    Example:
        >>> analyzer = DartLanguageAnalyzer()
        >>> res = analyzer.parse(Path("main.dart"), "class User { final int id; User(this.id); }")
        >>> syms = list(analyzer.extract_symbols(res))
        >>> any(s.kind == SymbolKind.CLASS for s in syms)
        True
    """
    language: ClassVar[str] = "dart"
    extensions: ClassVar[tuple[str, ...]] = (".dart",)

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse Dart source into AST-emulating representation.
        Example:
            >>> analyzer = DartLanguageAnalyzer()
            >>> res = analyzer.parse(Path("app.dart"), "void main() {}")
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
        """Extract Dart types, functions, methods, properties, and imports.
        Example:
            >>> analyzer = DartLanguageAnalyzer()
            >>> res = analyzer.parse(Path("service.dart"), "class Service { Future<void> init() async {} }")
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

        import_pattern = re.compile(r'^\s*(?:import|export)\s+[\'"]([^\'"]+)[\'"](?:\s+as\s+([a-zA-Z0-9_]+))?')
        type_pattern = re.compile(r'^\s*(?:(abstract|sealed|base|interface|final)\s+)?(class|mixin|enum|extension)\s+([a-zA-Z0-9_]+)(?:<[^>]+>)?(?:\s+extends\s+([a-zA-Z0-9_.,\s<>]+))?(?:\s+with\s+([a-zA-Z0-9_.,\s<>]+))?(?:\s+implements\s+([a-zA-Z0-9_.,\s<>]+))?')
        func_pattern = re.compile(r'^\s*(?:(static|override|factory)\s+)*(?:([a-zA-Z0-9_?<>]+)\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)(?:\s*async\s*)?(?:\s*\{|\s*=>)')
        prop_pattern = re.compile(r'^\s*(?:(static|final|const|late)\s+)*(?:([a-zA-Z0-9_?<>]+)\s+)?([a-zA-Z0-9_]+)(?:\s*=\s*[^;]+)?\s*;')

        current_type: str | None = None
        brace_depth = 0
        type_depth = 0

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue

            imp_match = import_pattern.match(line)
            if imp_match:
                imp_uri = imp_match.group(1)
                alias = imp_match.group(2) or imp_uri.split("/")[-1].replace(".dart", "")
                symbols.append(Symbol(
                    id=f"{file_path}::import::{imp_uri}",
                    name=alias,
                    qualified_name=imp_uri,
                    kind=SymbolKind.IMPORT,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=file_path,
                    signature=f"import '{imp_uri}'",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))
                continue

            type_match = type_pattern.match(line)
            if type_match:
                mod_str = type_match.group(1)
                type_kind = type_match.group(2)
                type_name = type_match.group(3)
                vis = Visibility.PRIVATE if type_name.startswith("_") else Visibility.PUBLIC
                kind = SymbolKind.INTERFACE if type_kind in ("mixin", "interface") else SymbolKind.CLASS
                modifiers = tuple(filter(None, [mod_str, type_kind]))
                sym_id = f"{file_path}::{type_name}"
                current_type = sym_id
                type_depth = brace_depth

                symbols.append(Symbol(
                    id=sym_id,
                    name=type_name,
                    qualified_name=type_name,
                    kind=kind,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=file_path,
                    signature=f"{type_kind} {type_name}",
                    visibility=vis,
                    modifiers=modifiers,
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            func_match = func_pattern.match(line)
            if func_match:
                func_mod = func_match.group(1)
                func_ret = func_match.group(2) or "void"
                func_name = func_match.group(3)
                func_args = func_match.group(4) or ""
                if func_name not in ("if", "for", "while", "switch", "catch"):
                    vis = Visibility.PRIVATE if func_name.startswith("_") else Visibility.PUBLIC
                    parent_id = current_type if current_type and brace_depth > type_depth else file_path
                    sym_id = f"{parent_id}::{func_name}"
                    symbols.append(Symbol(
                        id=sym_id,
                        name=func_name,
                        qualified_name=func_name,
                        kind=SymbolKind.FUNCTION,
                        language=self.language,
                        location=Location(file_path, line_idx, 0, line_idx, len(line)),
                        parent_id=parent_id,
                        signature=f"{func_ret} {func_name}({func_args})",
                        visibility=vis,
                        modifiers=tuple(filter(None, [func_mod])),
                        content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                    ))

            prop_match = prop_pattern.match(line)
            if prop_match and not line.strip().startswith("return") and not line.strip().startswith("import"):
                prop_mod = prop_match.group(1)
                prop_type = prop_match.group(2) or "dynamic"
                prop_name = prop_match.group(3)
                if prop_name and prop_name not in ("return", "break", "continue", "throw"):
                    vis = Visibility.PRIVATE if prop_name.startswith("_") else Visibility.PUBLIC
                    parent_id = current_type if current_type and brace_depth > type_depth else file_path
                    sym_id = f"{parent_id}::{prop_name}"
                    symbols.append(Symbol(
                        id=sym_id,
                        name=prop_name,
                        qualified_name=prop_name,
                        kind=SymbolKind.VARIABLE,
                        language=self.language,
                        location=Location(file_path, line_idx, 0, line_idx, len(line)),
                        parent_id=parent_id,
                        signature=f"{prop_type} {prop_name}",
                        visibility=vis,
                        modifiers=tuple(filter(None, [prop_mod])),
                        content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                    ))

            brace_depth += line.count("{") - line.count("}")
            if current_type and brace_depth <= type_depth:
                current_type = None

        return sorted(symbols, key=lambda s: (s.location.start_line if s.location else 0, s.name))

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract containment, inheritance, mixin, and import edges for Dart.
        Example:
            >>> analyzer = DartLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.dart"), "class Child extends Parent with Logger implements IService {}")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        file_path = parse.file_path
        symbol_map = {s.name: s for s in symbols}
        type_inherit_pattern = re.compile(r'^\s*(?:[a-zA-Z0-9_\s<>]+)?(?:class|mixin|enum|extension)\s+([a-zA-Z0-9_]+)(?:<[^>]+>)?(?:\s+extends\s+([a-zA-Z0-9_.,\s<>]+))?(?:\s+with\s+([a-zA-Z0-9_.,\s<>]+))?(?:\s+implements\s+([a-zA-Z0-9_.,\s<>]+))?')

        for s in symbols:
            if s.parent_id and s.parent_id != s.id:
                edges.append(Edge(
                    source_id=s.parent_id,
                    target_id=s.id,
                    kind=EdgeKind.CONTAINS,
                    weight=1.0,
                    confidence=1.0,
                    location=s.location,
                ))

        for line_idx, line in enumerate(parse.source.splitlines(), start=1):
            type_match = type_inherit_pattern.match(line)
            if type_match:
                type_name = type_match.group(1)
                extends_raw = type_match.group(2)
                with_raw = type_match.group(3)
                implements_raw = type_match.group(4)
                type_sym = symbol_map.get(type_name)
                if type_sym:
                    super_candidates = []
                    if extends_raw:
                        super_candidates.append(extends_raw.strip().split("<")[0].strip())
                    if with_raw:
                        for w in with_raw.split(","):
                            clean_w = w.strip().split("<")[0].strip()
                            if clean_w:
                                super_candidates.append(clean_w)
                    if implements_raw:
                        for imp in implements_raw.split(","):
                            clean_imp = imp.strip().split("<")[0].strip()
                            if clean_imp:
                                super_candidates.append(clean_imp)
                    for sup in super_candidates:
                        if sup and sup not in ("Object", "Widget", "StatelessWidget", "StatefulWidget"):
                            target_id = symbol_map[sup].id if sup in symbol_map else sup
                            edges.append(Edge(
                                source_id=type_sym.id,
                                target_id=target_id,
                                kind=EdgeKind.INHERITS,
                                weight=1.0,
                                confidence=0.9,
                                location=Location(file_path, line_idx, 0, line_idx, len(line)),
                            ))

            if line.strip().startswith("import ") or line.strip().startswith("export "):
                imp_match = re.search(r'[\'"]([^\'"]+)[\'"]', line)
                if imp_match:
                    target_uri = imp_match.group(1)
                    edges.append(Edge(
                        source_id=file_path,
                        target_id=target_uri,
                        kind=EdgeKind.IMPORTS,
                        weight=1.0,
                        confidence=1.0,
                        location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    ))

        return sorted(edges, key=lambda e: (e.source_id, e.target_id, e.kind.value))

    def resolve_import(self, ref: ImportRef, ctx: ResolveContext) -> Iterable[str]:
        """Resolve Dart imports (relative or package:) against workspace files.
        Example:
            >>> analyzer = DartLanguageAnalyzer()
            >>> from codeui.core.resolver import ResolveContext
            >>> ctx = ResolveContext(Path("."))
            >>> ref = ImportRef("lib/main.dart", "package:app/service.dart", None, False)
            >>> list(analyzer.resolve_import(ref, ctx))
            []
        """
        uri = ref.module_name
        if uri.startswith("package:"):
            parts = uri[len("package:"):].split("/", 1)
            if len(parts) > 1:
                pkg_sub = f"lib/{parts[1]}"
                cands = ctx.resolve_path(ref.from_file, pkg_sub, "dart")
                if cands:
                    return cands
                return ctx.resolve_path(ref.from_file, parts[1], "dart")
        return ctx.resolve_path(ref.from_file, uri, "dart")
