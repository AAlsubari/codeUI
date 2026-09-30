"""Scala language adapter for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class ScalaLanguageAnalyzer(LanguageAnalyzer):
    """Scala language adapter extracting traits, objects, case classes, defs, and vals.
    Example:
        >>> analyzer = ScalaLanguageAnalyzer()
        >>> res = analyzer.parse(Path("App.scala"), "case class User(id: Long, name: String)")
        >>> syms = list(analyzer.extract_symbols(res))
        >>> any(s.kind == SymbolKind.CLASS for s in syms)
        True
    """
    language: ClassVar[str] = "scala"
    extensions: ClassVar[tuple[str, ...]] = (".scala", ".sc")

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse Scala source into AST-emulating representation.
        Example:
            >>> analyzer = ScalaLanguageAnalyzer()
            >>> res = analyzer.parse(Path("Main.scala"), "object Main extends App {}")
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
        """Extract Scala packages, classes, traits, objects, defs, and vals.
        Example:
            >>> analyzer = ScalaLanguageAnalyzer()
            >>> res = analyzer.parse(Path("Service.scala"), "trait Service { def run(): Unit }")
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

        package_pattern = re.compile(r'^\s*package\s+([a-zA-Z0-9_.]+)')
        import_pattern = re.compile(r'^\s*import\s+([a-zA-Z0-9_.*{}]+)')
        type_pattern = re.compile(r'^\s*(?:(private|protected)(?:\[[a-zA-Z0-9_]+\])?\s+)?(?:(sealed|abstract|final|case|implicit|lazy)\s+)*(class|trait|object|enum)\s+([a-zA-Z0-9_]+)(?:\[[^\]]+\])?(?:\s*\([^)]*\))?(?:\s+extends\s+([a-zA-Z0-9_.,\s\[\]()]+))?(?:\s+with\s+([a-zA-Z0-9_.,\s\[\]()]+))?')
        def_pattern = re.compile(r'^\s*(?:(private|protected)(?:\[[a-zA-Z0-9_]+\])?\s+)?(?:(override|final|implicit|def)\s+)*def\s+([a-zA-Z0-9_=+<>*/&|~^%-]+)(?:\[[^\]]+\])?\s*(?:\(([^)]*)\))?(?:\s*:\s*([a-zA-Z0-9_?<>,\s\[\]]+))?')
        val_pattern = re.compile(r'^\s*(?:(private|protected)(?:\[[a-zA-Z0-9_]+\])?\s+)?(?:(override|final|implicit|lazy)\s+)*(val|var)\s+([a-zA-Z0-9_]+)(?:\s*:\s*([a-zA-Z0-9_?<>,\s\[\]]+))?')

        current_package = ""
        current_type: str | None = None
        brace_depth = 0
        type_depth = 0

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue

            pkg_match = package_pattern.match(line)
            if pkg_match:
                current_package = pkg_match.group(1)
                symbols.append(Symbol(
                    id=f"{file_path}::package::{current_package}",
                    name=current_package,
                    qualified_name=current_package,
                    kind=SymbolKind.NAMESPACE,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=file_path,
                    signature=f"package {current_package}",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))
                continue

            imp_match = import_pattern.match(line)
            if imp_match:
                imp_name = imp_match.group(1)
                symbols.append(Symbol(
                    id=f"{file_path}::import::{imp_name}",
                    name=imp_name.split(".")[-1],
                    qualified_name=imp_name,
                    kind=SymbolKind.IMPORT,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=file_path,
                    signature=f"import {imp_name}",
                    visibility=Visibility.PUBLIC,
                    modifiers=(),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))
                continue

            type_match = type_pattern.match(line)
            if type_match:
                vis_str = type_match.group(1) or "public"
                mod_str = type_match.group(2)
                type_kind = type_match.group(3)
                type_name = type_match.group(4)
                vis = Visibility.PRIVATE if vis_str == "private" else (Visibility.PROTECTED if vis_str == "protected" else Visibility.PUBLIC)
                kind = SymbolKind.INTERFACE if type_kind == "trait" else SymbolKind.CLASS
                modifiers = tuple(filter(None, [mod_str, type_kind]))
                qual_prefix = f"{current_package}." if current_package else ""
                sym_id = f"{file_path}::{type_name}"
                current_type = sym_id
                type_depth = brace_depth

                symbols.append(Symbol(
                    id=sym_id,
                    name=type_name,
                    qualified_name=f"{qual_prefix}{type_name}",
                    kind=kind,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=file_path,
                    signature=f"{vis_str} {type_kind} {type_name}",
                    visibility=vis,
                    modifiers=modifiers,
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            def_match = def_pattern.match(line)
            if def_match:
                vis_str = def_match.group(1) or "public"
                def_mod = def_match.group(2)
                def_name = def_match.group(3)
                def_args = def_match.group(4) or ""
                def_ret = def_match.group(5) or "Unit"
                vis = Visibility.PRIVATE if vis_str == "private" else (Visibility.PROTECTED if vis_str == "protected" else Visibility.PUBLIC)
                parent_id = current_type if current_type and brace_depth > type_depth else file_path
                sym_id = f"{parent_id}::{def_name}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=def_name,
                    qualified_name=f"{current_package}.{def_name}" if current_package else def_name,
                    kind=SymbolKind.FUNCTION,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=parent_id,
                    signature=f"def {def_name}({def_args}): {def_ret}",
                    visibility=vis,
                    modifiers=tuple(filter(None, [def_mod])),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            val_match = val_pattern.match(line)
            if val_match:
                vis_str = val_match.group(1) or "public"
                val_mod = val_match.group(2)
                val_or_var = val_match.group(3)
                val_name = val_match.group(4)
                val_type = val_match.group(5) or "Any"
                vis = Visibility.PRIVATE if vis_str == "private" else (Visibility.PROTECTED if vis_str == "protected" else Visibility.PUBLIC)
                parent_id = current_type if current_type and brace_depth > type_depth else file_path
                sym_id = f"{parent_id}::{val_name}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=val_name,
                    qualified_name=f"{current_package}.{val_name}" if current_package else val_name,
                    kind=SymbolKind.VARIABLE,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=parent_id,
                    signature=f"{val_or_var} {val_name}: {val_type}",
                    visibility=vis,
                    modifiers=tuple(filter(None, [val_mod, val_or_var])),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            brace_depth += line.count("{") - line.count("}")
            if current_type and brace_depth <= type_depth:
                current_type = None

        return sorted(symbols, key=lambda s: (s.location.start_line if s.location else 0, s.name))

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract containment, inheritance, and import edges for Scala.
        Example:
            >>> analyzer = ScalaLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.scala"), "class Child extends Parent with TraitA")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        file_path = parse.file_path
        symbol_map = {s.name: s for s in symbols}
        type_inherit_pattern = re.compile(r'^\s*(?:[a-zA-Z0-9_\s<>]+)?(?:class|trait|object)\s+([a-zA-Z0-9_]+)(?:\[[^\]]+\])?(?:\s*\([^)]*\))?(?:\s+extends\s+([a-zA-Z0-9_.,\s\[\]()]+))?(?:\s+with\s+([a-zA-Z0-9_.,\s\[\]()]+))?')

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
                type_sym = symbol_map.get(type_name)
                if type_sym:
                    super_candidates = []
                    if extends_raw:
                        super_candidates.append(extends_raw.strip().split("(")[0].split("[")[0].strip())
                    if with_raw:
                        for w in with_raw.split("with"):
                            clean_w = w.strip().split("(")[0].split("[")[0].strip()
                            if clean_w:
                                super_candidates.append(clean_w)
                    for sup in super_candidates:
                        if sup and sup not in ("App", "Any", "Serializable", "Product"):
                            target_id = symbol_map[sup].id if sup in symbol_map else sup
                            edges.append(Edge(
                                source_id=type_sym.id,
                                target_id=target_id,
                                kind=EdgeKind.INHERITS,
                                weight=1.0,
                                confidence=0.9,
                                location=Location(file_path, line_idx, 0, line_idx, len(line)),
                            ))

            if line.strip().startswith("import "):
                imp_parts = line.strip().replace("import ", "").rstrip(";").split()
                if imp_parts:
                    target_mod = imp_parts[0].rstrip("._")
                    edges.append(Edge(
                        source_id=file_path,
                        target_id=target_mod,
                        kind=EdgeKind.IMPORTS,
                        weight=1.0,
                        confidence=1.0,
                        location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    ))

        return sorted(edges, key=lambda e: (e.source_id, e.target_id, e.kind.value))

    def resolve_import(self, ref: ImportRef, ctx: ResolveContext) -> Iterable[str]:
        """Resolve Scala package or object imports against project files.
        Example:
            >>> analyzer = ScalaLanguageAnalyzer()
            >>> from codeui.core.resolver import ResolveContext
            >>> ctx = ResolveContext(Path("."))
            >>> ref = ImportRef("src/Main.scala", "com.example.Service", None, False)
            >>> list(analyzer.resolve_import(ref, ctx))
            []
        """
        mod_name = ref.module_name.rstrip("._")
        candidates = ctx.resolve_path(ref.from_file, mod_name, "scala")
        if not candidates and "." in mod_name:
            leaf = mod_name.split(".")[-1]
            candidates = ctx.resolve_path(ref.from_file, leaf, "scala")
        return candidates
