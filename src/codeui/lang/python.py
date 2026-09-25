"""Python language adapter using standard library ast."""
import ast
import hashlib
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Sequence, Tuple
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.core.resolver import ResolveContext
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

class PythonLanguageAnalyzer(LanguageAnalyzer):
    """Python language analyzer using standard library ast.
    Example:
        >>> analyzer = PythonLanguageAnalyzer()
        >>> res = analyzer.parse(Path("test.py"), "def hello(): pass")
        >>> syms = list(analyzer.extract_symbols(res))
        >>> len(syms) >= 1
        True
    """
    language: ClassVar[str] = "python"
    extensions: ClassVar[tuple[str, ...]] = (".py", ".pyi")

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse Python source text into ast.AST object.
        Example:
            >>> analyzer = PythonLanguageAnalyzer()
            >>> res = analyzer.parse(Path("a.py"), "x = 1")
            >>> res.errors
            []
        """
        content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        errors: List[str] = []
        parsed_ast: Any = None
        try:
            parsed_ast = ast.parse(source, filename=str(path))
        except SyntaxError as e:
            errors.append(f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}")
        return ParseResult(
            file_path=str(path),
            source=source,
            ast=parsed_ast,
            content_hash=content_hash,
            errors=errors,
        )

    def extract_symbols(self, parse: ParseResult) -> Iterable[Symbol]:
        """Extract all symbols from parsed Python AST.
        Example:
            >>> analyzer = PythonLanguageAnalyzer()
            >>> res = analyzer.parse(Path("a.py"), "def foo(): pass")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> syms[0].kind == SymbolKind.FILE
            True
        """
        if parse.ast is None:
            return []
        symbols: List[Symbol] = []
        file_path = parse.file_path
        lines = parse.source.splitlines()
        max_line = len(lines) if lines else 1
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
        self._walk_ast(parse.ast, file_path, file_path, "", symbols)
        return symbols

    def _walk_ast(self, node: ast.AST, file_path: str, parent_id: str, scope_prefix: str, symbols: List[Symbol]) -> None:
        """Traverse AST nodes recursively to construct Symbol records."""
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qname = f"{scope_prefix}.{child.name}" if scope_prefix else child.name
                sym_id = f"{file_path}::{qname}"
                loc = Location(
                    file_id=file_path,
                    start_line=child.lineno,
                    start_col=child.col_offset,
                    end_line=getattr(child, "end_lineno", child.lineno),
                    end_col=getattr(child, "end_col_offset", child.col_offset),
                )
                vis = Visibility.PRIVATE if child.name.startswith("_") else Visibility.PUBLIC
                body_str = ast.dump(child)
                s = Symbol(
                    id=sym_id,
                    name=child.name,
                    qualified_name=qname,
                    kind=SymbolKind.CLASS,
                    language=self.language,
                    location=loc,
                    parent_id=parent_id,
                    signature=f"class {child.name}",
                    visibility=vis,
                    modifiers=(),
                    content_hash=hashlib.sha256(body_str.encode()).hexdigest()[:16],
                )
                symbols.append(s)
                self._walk_ast(child, file_path, sym_id, qname, symbols)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qname = f"{scope_prefix}.{child.name}" if scope_prefix else child.name
                sym_id = f"{file_path}::{qname}"
                kind = SymbolKind.METHOD if scope_prefix and "." in scope_prefix or any(s.kind == SymbolKind.CLASS for s in symbols if s.id == parent_id) else SymbolKind.FUNCTION
                loc = Location(
                    file_id=file_path,
                    start_line=child.lineno,
                    start_col=child.col_offset,
                    end_line=getattr(child, "end_lineno", child.lineno),
                    end_col=getattr(child, "end_col_offset", child.col_offset),
                )
                vis = Visibility.PRIVATE if child.name.startswith("_") else Visibility.PUBLIC
                body_str = ast.dump(child)
                s = Symbol(
                    id=sym_id,
                    name=child.name,
                    qualified_name=qname,
                    kind=kind,
                    language=self.language,
                    location=loc,
                    parent_id=parent_id,
                    signature=f"def {child.name}(...)",
                    visibility=vis,
                    modifiers=("async",) if isinstance(child, ast.AsyncFunctionDef) else (),
                    content_hash=hashlib.sha256(body_str.encode()).hexdigest()[:16],
                )
                symbols.append(s)
                self._walk_ast(child, file_path, sym_id, qname, symbols)

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract relationship edges from parse AST and symbols.
        Example:
            >>> analyzer = PythonLanguageAnalyzer()
            >>> res = analyzer.parse(Path("a.py"), "def f(): pass\\ndef g(): f()")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> any(e.source_id == "a.py::g" and e.target_id == "a.py::f" for e in edges)
            True
        """
        if parse.ast is None:
            return []
        edges: List[Edge] = []
        sym_map = {s.id: s for s in symbols}
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
        import_map: Dict[str, str] = {}
        for node in ast.walk(parse.ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    import_map[local_name] = f"module::{alias.name}"
                    weight = float(self._count_symbol_usages(parse.source, local_name))
                    edges.append(Edge(
                        source_id=parse.file_path,
                        target_id=f"module::{alias.name}",
                        kind=EdgeKind.IMPORTS,
                        weight=weight,
                        confidence=1.0,
                        location=Location(parse.file_path, node.lineno, node.col_offset, node.lineno, node.col_offset),
                    ))
            elif isinstance(node, ast.ImportFrom):
                level = getattr(node, "level", 0) or 0
                dots = "." * level if level > 0 else ""
                raw_mod = node.module or ""
                mod_name = f"{dots}{raw_mod}" if dots else raw_mod
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    target = f"module::{mod_name}.{alias.name}" if mod_name else f"module::{alias.name}"
                    import_map[local_name] = target
                    weight = float(self._count_symbol_usages(parse.source, local_name))
                    edges.append(Edge(
                        source_id=parse.file_path,
                        target_id=target,
                        kind=EdgeKind.IMPORTS,
                        weight=weight,
                        confidence=1.0,
                        location=Location(parse.file_path, node.lineno, node.col_offset, node.lineno, node.col_offset),
                    ))
        class_names = {s.name for s in symbols if s.kind == SymbolKind.CLASS}
        def walk_calls(node: ast.AST, current_scope: str, class_scope: str, locals_in_scope: set[str]) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    class_sym_id = f"{parse.file_path}::{child.name}"
                    for base in child.bases:
                        if isinstance(base, ast.Name):
                            target_id = f"{parse.file_path}::{base.id}"
                            edges.append(Edge(
                                source_id=class_sym_id,
                                target_id=target_id,
                                kind=EdgeKind.INHERITS,
                                weight=1.0,
                                confidence=0.9,
                                location=Location(parse.file_path, base.lineno, base.col_offset, base.lineno, base.col_offset + len(base.id)),
                            ))
                    walk_calls(child, class_sym_id, child.name, set())
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qname = f"{class_scope}.{child.name}" if class_scope else child.name
                    func_sym_id = f"{parse.file_path}::{qname}"
                    new_locals = set(locals_in_scope)
                    for arg in getattr(child.args, "posonlyargs", []) + getattr(child.args, "args", []) + getattr(child.args, "kwonlyargs", []):
                        if hasattr(arg, "arg"):
                            new_locals.add(arg.arg)
                    if getattr(child.args, "vararg", None):
                        new_locals.add(child.args.vararg.arg)
                    if getattr(child.args, "kwarg", None):
                        new_locals.add(child.args.kwarg.arg)
                    for subnode in ast.walk(child):
                        if isinstance(subnode, ast.Assign):
                            for target in subnode.targets:
                                if isinstance(target, ast.Name):
                                    new_locals.add(target.id)
                        elif isinstance(subnode, ast.AnnAssign):
                            if isinstance(subnode.target, ast.Name):
                                new_locals.add(subnode.target.id)
                    walk_calls(child, func_sym_id, class_scope, new_locals)
                elif isinstance(child, ast.Call):
                    caller_id = current_scope if current_scope else parse.file_path
                    if isinstance(child.func, ast.Name):
                        callee_name = child.func.id
                        if callee_name not in locals_in_scope:
                            target_id = import_map.get(callee_name, f"{parse.file_path}::{callee_name}")
                            weight = float(self._count_symbol_usages(parse.source, callee_name))
                            edges.append(Edge(
                                source_id=caller_id,
                                target_id=target_id,
                                kind=EdgeKind.CALLS,
                                weight=weight,
                                confidence=0.85,
                                location=Location(parse.file_path, child.lineno, child.col_offset, child.lineno, child.col_offset + len(callee_name)),
                            ))
                    elif isinstance(child.func, ast.Attribute):
                        attr_name = child.func.attr
                        target_id = None
                        if isinstance(child.func.value, ast.Name):
                            val_name = child.func.value.id
                            if val_name in ("self", "cls") and class_scope:
                                target_id = f"{parse.file_path}::{class_scope}.{attr_name}"
                            elif val_name in import_map:
                                target_id = f"{import_map[val_name]}.{attr_name}"
                            elif val_name in class_names:
                                target_id = f"{parse.file_path}::{val_name}.{attr_name}"
                        if target_id:
                            weight = float(self._count_symbol_usages(parse.source, attr_name))
                            edges.append(Edge(
                                source_id=caller_id,
                                target_id=target_id,
                                kind=EdgeKind.CALLS,
                                weight=weight,
                                confidence=0.8,
                                location=Location(parse.file_path, child.lineno, child.col_offset, child.lineno, child.col_offset + len(attr_name)),
                            ))
                    walk_calls(child, current_scope, class_scope, locals_in_scope)
                else:
                    walk_calls(child, current_scope, class_scope, locals_in_scope)
        walk_calls(parse.ast, "", "", set())
        return edges

    def _count_symbol_usages(self, source: str, symbol_name: str) -> int:
        if not symbol_name or symbol_name == "*":
            return 1
        pattern = r"\b" + re.escape(symbol_name) + r"\b"
        count = 0
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ", "#")):
                continue
            count += len(re.findall(pattern, line))
        return max(1, count)

    def resolve_import(self, ref: ImportRef, ctx: ResolveContext) -> Iterable[str]:
        """Resolve Python import module path to candidate files.
        Example:
            >>> analyzer = PythonLanguageAnalyzer()
            >>> ctx = ResolveContext(Path("."))
            >>> ref = ImportRef("app.py", "utils", None, False)
            >>> isinstance(list(analyzer.resolve_import(ref, ctx)), list)
            True
        """
        return ctx.resolve_path(ref.file_path, ref.module_name, "python")
