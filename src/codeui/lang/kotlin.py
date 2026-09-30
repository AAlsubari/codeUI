"""Kotlin language analyzer for codeui."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence, TYPE_CHECKING
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

if TYPE_CHECKING:
    from codeui.core.resolver import ResolveContext

class KotlinLanguageAnalyzer(LanguageAnalyzer):
    """Kotlin language adapter extracting classes, interfaces, objects, funs, and properties.
    Example:
        >>> analyzer = KotlinLanguageAnalyzer()
        >>> res = analyzer.parse(Path("Main.kt"), "data class User(val id: Long, val name: String)")
        >>> syms = list(analyzer.extract_symbols(res))
        >>> any(s.kind == SymbolKind.CLASS for s in syms)
        True
    """
    language: ClassVar[str] = "kotlin"
    extensions: ClassVar[tuple[str, ...]] = (".kt", ".kts")

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse Kotlin source into AST-emulating representation.
        Example:
            >>> analyzer = KotlinLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.kt"), "fun main() {}")
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
        """Extract Kotlin packages, classes, interfaces, objects, functions, and properties.
        Example:
            >>> analyzer = KotlinLanguageAnalyzer()
            >>> res = analyzer.parse(Path("Greeter.kt"), "class Greeter { fun greet(): String = \\"hi\\" }")
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
        import_pattern = re.compile(r'^\s*import\s+([a-zA-Z0-9_.*]+)')
        class_pattern = re.compile(r'^\s*(?:(public|private|protected|internal)\s+)?(?:(data|sealed|open|abstract|enum|annotation|inner)\s+)?(class|interface|object)\s+([a-zA-Z0-9_]+)(?:<[^>]+>)?(?:\s*\([^)]*\))?(?:\s*:\s*([a-zA-Z0-9_.,\s<>()]+))?')
        companion_pattern = re.compile(r'^\s*companion\s+object(?:\s+([a-zA-Z0-9_]+))?')
        fun_pattern = re.compile(r'^\s*(?:(public|private|protected|internal)\s+)?(?:(override|open|abstract|suspend|inline|operator|infix)\s+)*fun\s+(?:<[^>]+>\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)(?:\s*:\s*([a-zA-Z0-9_?<>,\s]+))?')
        property_pattern = re.compile(r'^\s*(?:(public|private|protected|internal)\s+)?(?:(override|open|abstract|const)\s+)*(val|var)\s+([a-zA-Z0-9_]+)(?:\s*:\s*([a-zA-Z0-9_?<>,\s]+))?')

        current_package = ""
        current_class: str | None = None
        brace_depth = 0
        class_depth = 0

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue

            pkg_match = package_pattern.match(line)
            if pkg_match:
                current_package = pkg_match.group(1)
                pkg_sym = Symbol(
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
                )
                symbols.append(pkg_sym)
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

            comp_match = companion_pattern.match(line)
            if comp_match:
                comp_name = comp_match.group(1) or "Companion"
                parent_id = current_class or file_path
                sym_id = f"{file_path}::{comp_name}" if not current_class else f"{current_class}::{comp_name}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=comp_name,
                    qualified_name=f"{current_package}.{comp_name}" if current_package else comp_name,
                    kind=SymbolKind.CLASS,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=parent_id,
                    signature=f"companion object {comp_name}",
                    visibility=Visibility.PUBLIC,
                    modifiers=("companion",),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            class_match = class_pattern.match(line)
            if class_match:
                vis_str = class_match.group(1) or "public"
                mod_str = class_match.group(2)
                type_kind = class_match.group(3)
                class_name = class_match.group(4)
                vis = Visibility.PRIVATE if vis_str == "private" else (Visibility.PROTECTED if vis_str in ("protected", "internal") else Visibility.PUBLIC)
                kind = SymbolKind.INTERFACE if type_kind == "interface" else SymbolKind.CLASS
                modifiers = tuple(filter(None, [mod_str, type_kind]))
                qual_prefix = f"{current_package}." if current_package else ""
                sym_id = f"{file_path}::{class_name}"
                current_class = sym_id
                class_depth = brace_depth

                symbols.append(Symbol(
                    id=sym_id,
                    name=class_name,
                    qualified_name=f"{qual_prefix}{class_name}",
                    kind=kind,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=file_path,
                    signature=f"{vis_str} {type_kind} {class_name}",
                    visibility=vis,
                    modifiers=modifiers,
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            fun_match = fun_pattern.match(line)
            if fun_match:
                vis_str = fun_match.group(1) or "public"
                fun_mod = fun_match.group(2)
                fun_name = fun_match.group(3)
                fun_args = fun_match.group(4)
                fun_ret = fun_match.group(5) or "Unit"
                vis = Visibility.PRIVATE if vis_str == "private" else (Visibility.PROTECTED if vis_str in ("protected", "internal") else Visibility.PUBLIC)
                parent_id = current_class if current_class and brace_depth > class_depth else file_path
                sym_id = f"{parent_id}::{fun_name}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=fun_name,
                    qualified_name=f"{current_package}.{fun_name}" if current_package else fun_name,
                    kind=SymbolKind.FUNCTION,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=parent_id,
                    signature=f"fun {fun_name}({fun_args}): {fun_ret}",
                    visibility=vis,
                    modifiers=tuple(filter(None, [fun_mod])),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            prop_match = property_pattern.match(line)
            if prop_match:
                vis_str = prop_match.group(1) or "public"
                prop_mod = prop_match.group(2)
                val_or_var = prop_match.group(3)
                prop_name = prop_match.group(4)
                prop_type = prop_match.group(5) or "Any"
                vis = Visibility.PRIVATE if vis_str == "private" else (Visibility.PROTECTED if vis_str in ("protected", "internal") else Visibility.PUBLIC)
                parent_id = current_class if current_class and brace_depth > class_depth else file_path
                sym_id = f"{parent_id}::{prop_name}"
                symbols.append(Symbol(
                    id=sym_id,
                    name=prop_name,
                    qualified_name=f"{current_package}.{prop_name}" if current_package else prop_name,
                    kind=SymbolKind.VARIABLE,
                    language=self.language,
                    location=Location(file_path, line_idx, 0, line_idx, len(line)),
                    parent_id=parent_id,
                    signature=f"{val_or_var} {prop_name}: {prop_type}",
                    visibility=vis,
                    modifiers=tuple(filter(None, [prop_mod, val_or_var])),
                    content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest()[:16],
                ))

            brace_depth += line.count("{") - line.count("}")
            if current_class and brace_depth <= class_depth:
                current_class = None

        return sorted(symbols, key=lambda s: (s.location.start_line if s.location else 0, s.name))

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract containment, inheritance, imports, and calls edges for Kotlin.
        Example:
            >>> analyzer = KotlinLanguageAnalyzer()
            >>> res = analyzer.parse(Path("App.kt"), "class Child : Parent()")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        file_path = parse.file_path
        symbol_map = {s.name: s for s in symbols}
        class_pattern = re.compile(r'^\s*(?:[a-zA-Z0-9_\s<>]+)?(?:class|interface|object)\s+([a-zA-Z0-9_]+)(?:<[^>]+>)?(?:\s*\([^)]*\))?\s*:\s*([a-zA-Z0-9_.,\s<>()]+)')

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
            class_match = class_pattern.match(line)
            if class_match:
                cls_name = class_match.group(1)
                super_types_raw = class_match.group(2)
                cls_sym = symbol_map.get(cls_name)
                if cls_sym:
                    for super_raw in super_types_raw.split(","):
                        clean_super = super_raw.strip().split("(")[0].split("<")[0].strip()
                        if clean_super and clean_super not in ("Any", "Serializable"):
                            target_id = symbol_map[clean_super].id if clean_super in symbol_map else clean_super
                            edges.append(Edge(
                                source_id=cls_sym.id,
                                target_id=target_id,
                                kind=EdgeKind.INHERITS,
                                weight=1.0,
                                confidence=0.9,
                                location=Location(file_path, line_idx, 0, line_idx, len(line)),
                            ))

            if line.strip().startswith("import "):
                imp_parts = line.strip().replace("import ", "").rstrip(";").split()
                if imp_parts:
                    target_mod = imp_parts[0]
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
        """Resolve Kotlin package or class imports against workspace files.
        Example:
            >>> analyzer = KotlinLanguageAnalyzer()
            >>> from codeui.core.resolver import ResolveContext
            >>> ctx = ResolveContext(Path("."))
            >>> ref = ImportRef("app/Main.kt", "com.example.User", None, False)
            >>> list(analyzer.resolve_import(ref, ctx))
            []
        """
        mod_name = ref.module_name.rstrip(".*")
        candidates = ctx.resolve_path(ref.from_file, mod_name, "kotlin")
        if not candidates and "." in mod_name:
            leaf = mod_name.split(".")[-1]
            candidates = ctx.resolve_path(ref.from_file, leaf, "kotlin")
        return candidates
