"""Swift language analyzer for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class SwiftLanguageAnalyzer(LanguageAnalyzer):
    """Swift language adapter extracting protocols, classes, structs, enums, actors, funcs, and vars.
    Example:
        >>> analyzer = SwiftLanguageAnalyzer()
        >>> res = analyzer.parse(Path("Model.swift"), "struct User: Codable { let id: Int }")
        >>> syms = list(analyzer.extract_symbols(res))
        >>> any(s.kind == SymbolKind.CLASS for s in syms)
        True
    """
    language: ClassVar[str] = "swift"
    extensions: ClassVar[tuple[str, ...]] = (".swift",)

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse Swift source into AST-emulating representation.
        Example:
            >>> analyzer = SwiftLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.swift"), "func run() {}")
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
        """Extract Swift types, functions, properties, extensions, and imports.
        Example:
            >>> analyzer = SwiftLanguageAnalyzer()
            >>> res = analyzer.parse(Path("Service.swift"), "class Service { func fetch() {} }")
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

        import_pattern = re.compile(r'^\s*import\s+([a-zA-Z0-9_]+)')
        type_pattern = re.compile(r'^\s*(?:(public|private|fileprivate|internal|open)\s+)?(?:(final)\s+)?(class|struct|protocol|enum|actor)\s+([a-zA-Z0-9_]+)(?:<[^>]+>)?(?:\s*:\s*([a-zA-Z0-9_.,\s<>]+))?')
        extension_pattern = re.compile(r'^\s*extension\s+([a-zA-Z0-9_]+)(?:\s*:\s*([a-zA-Z0-9_.,\s<>]+))?')
        func_pattern = re.compile(r'^\s*(?:(public|private|fileprivate|internal|open)\s+)?(?:(static|class|override|mutating|async|throws)\s+)*(func|init)\s*(?:<[^>]+>\s*)?([a-zA-Z0-9_]+)?\s*\(([^)]*)\)(?:\s*(?:async\s*)?(?:throws\s*)?->\s*([a-zA-Z0-9_?<>,\s\[\]:]+))?')
        var_pattern = re.compile(r'^\s*(?:(public|private|fileprivate|internal|open)\s+)?(?:(static|class|weak|unowned)\s+)*(let|var)\s+([a-zA-Z0-9_]+)(?:\s*:\s*([a-zA-Z0-9_?<>,\s\[\]:]+))?')

        current_type: str | None = None
        brace_depth = 0
        type_depth = 0

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue

            imp_match = import_pattern.match(line)
            if imp_match:
                mod_name = imp_match.group(1)
                symbols.append(Symbol(
                    id=f"{file_path}::import::{mod_name}",
                    name=mod_name,
                    qualified_name=mod_name,
                    kind=SymbolKind.IMPORT,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=file_path,
                    signature=f"import {mod_name}",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))
                continue

            ext_match = extension_pattern.match(line)
            if ext_match:
                ext_name = ext_match.group(1)
                sym_id = f"{file_path}::extension_{ext_name}_{line_idx}"
                current_type = sym_id
                type_depth = brace_depth
                symbols.append(Symbol(
                    id=sym_id,
                    name=ext_name,
                    qualified_name=ext_name,
                    kind=SymbolKind.CLASS,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=file_path,
                    signature=f"extension {ext_name}",
                    visibility=Visibility.PUBLIC,
                    modifiers=("extension",),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            type_match = type_pattern.match(line)
            if type_match:
                vis_str = type_match.group(1) or "internal"
                final_mod = type_match.group(2)
                type_kind = type_match.group(3)
                type_name = type_match.group(4)
                vis = Visibility.PRIVATE if vis_str in ("private", "fileprivate") else (Visibility.PROTECTED if vis_str == "internal" else Visibility.PUBLIC)
                kind = SymbolKind.INTERFACE if type_kind == "protocol" else SymbolKind.CLASS
                modifiers = tuple(filter(None, [vis_str, final_mod, type_kind]))
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
                    signature=f"{vis_str} {type_kind} {type_name}",
                    visibility=vis,
                    modifiers=modifiers,
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            func_match = func_pattern.match(line)
            if func_match:
                vis_str = func_match.group(1) or "internal"
                func_mod = func_match.group(2)
                is_init = func_match.group(3) == "init"
                func_name = "init" if is_init else (func_match.group(4) or "anonymous")
                func_args = func_match.group(5) or ""
                func_ret = func_match.group(6) or "Void"
                vis = Visibility.PRIVATE if vis_str in ("private", "fileprivate") else (Visibility.PROTECTED if vis_str == "internal" else Visibility.PUBLIC)
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
                    signature=f"func {func_name}({func_args}) -> {func_ret}" if not is_init else f"init({func_args})",
                    visibility=vis,
                    modifiers=tuple(filter(None, [vis_str, func_mod])),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            var_match = var_pattern.match(line)
            if var_match:
                vis_str = var_match.group(1) or "internal"
                var_mod = var_match.group(2)
                let_or_var = var_match.group(3)
                var_name = var_match.group(4)
                var_type = var_match.group(5) or "Any"
                vis = Visibility.PRIVATE if vis_str in ("private", "fileprivate") else (Visibility.PROTECTED if vis_str == "internal" else Visibility.PUBLIC)
                parent_id = current_type if current_type and brace_depth > type_depth else file_path
                sym_id = f"{parent_id}::{var_name}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=var_name,
                    qualified_name=var_name,
                    kind=SymbolKind.VARIABLE,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=parent_id,
                    signature=f"{let_or_var} {var_name}: {var_type}",
                    visibility=vis,
                    modifiers=tuple(filter(None, [vis_str, var_mod, let_or_var])),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            brace_depth += line.count("{") - line.count("}")
            if current_type and brace_depth <= type_depth:
                current_type = None

        return sorted(symbols, key=lambda s: (s.location.start_line if s.location else 0, s.name))

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract containment, protocol adoption, class inheritance, and import edges for Swift.
        Example:
            >>> analyzer = SwiftLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.swift"), "class Child: Parent {}")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        file_path = parse.file_path
        symbol_map = {s.name: s for s in symbols}
        type_inherit_pattern = re.compile(r'^\s*(?:[a-zA-Z0-9_\s<>]+)?(?:class|struct|protocol|enum|actor|extension)\s+([a-zA-Z0-9_]+)(?:<[^>]+>)?\s*:\s*([a-zA-Z0-9_.,\s<>]+)')

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
                super_types_raw = type_match.group(2)
                type_sym = symbol_map.get(type_name)
                if type_sym:
                    for super_raw in super_types_raw.split(","):
                        clean_super = super_raw.strip().split("<")[0].strip()
                        if clean_super and clean_super not in ("AnyObject", "Codable", "Equatable", "Hashable"):
                            target_id = symbol_map[clean_super].id if clean_super in symbol_map else clean_super
                            edges.append(Edge(
                                source_id=type_sym.id,
                                target_id=target_id,
                                kind=EdgeKind.INHERITS,
                                weight=1.0,
                                confidence=0.9,
                                location=Location(file_path, line_idx, 0, line_idx, len(line)),
                            ))

            if line.strip().startswith("import "):
                imp_mod = line.strip().replace("import ", "").split()[0]
                edges.append(Edge(
                    source_id=file_path,
                    target_id=imp_mod,
                    kind=EdgeKind.IMPORTS,
                    weight=1.0,
                    confidence=1.0,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                ))

        return sorted(edges, key=lambda e: (e.source_id, e.target_id, e.kind.value))

    def resolve_import(self, ref: ImportRef, ctx: ResolveContext) -> Iterable[str]:
        """Resolve Swift module imports against workspace packages or files.
        Example:
            >>> analyzer = SwiftLanguageAnalyzer()
            >>> from codeui.core.resolver import ResolveContext
            >>> ctx = ResolveContext(Path("."))
            >>> ref = ImportRef("Sources/App/main.swift", "SharedKit", None, False)
            >>> list(analyzer.resolve_import(ref, ctx))
            []
        """
        return ctx.resolve_path(ref.from_file, ref.module_name, "swift")
