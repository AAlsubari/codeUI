"""TypeScript/JavaScript language adapter for codeui."""
import hashlib
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Sequence
from codeui.core.ir import Edge, EdgeKind, Location, Symbol, SymbolKind, Visibility
from codeui.core.resolver import ResolveContext
from codeui.lang.base import ImportRef, LanguageAnalyzer, ParseResult

class TSLanguageAnalyzer(LanguageAnalyzer):
    """TypeScript and JavaScript language adapter.
    Example:
        >>> analyzer = TSLanguageAnalyzer()
        >>> res = analyzer.parse(Path("app.ts"), "export function greet(name: string) { return 'hello ' + name; }")
        >>> syms = list(analyzer.extract_symbols(res))
        >>> len(syms) >= 2
        True
    """
    language: ClassVar[str] = "typescript"
    extensions: ClassVar[tuple[str, ...]] = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

    def parse(self, path: Path, source: str) -> ParseResult:
        """Parse TypeScript / JavaScript file source.
        Example:
            >>> analyzer = TSLanguageAnalyzer()
            >>> res = analyzer.parse(Path("main.ts"), "const x = 10;")
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
        """Extract functions, classes, interfaces, types, imports, and variables.
        Example:
            >>> analyzer = TSLanguageAnalyzer()
            >>> res = analyzer.parse(Path("index.ts"), "class User { id: number; }")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> any(s.kind == SymbolKind.CLASS for s in syms)
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
        class_pattern = re.compile(r'(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_$]+)(?:<[^>]+>)?(?:\s+extends\s+([A-Za-z0-9_$]+))?')
        interface_pattern = re.compile(r'(?:export\s+)?interface\s+([A-Za-z0-9_$]+)(?:<[^>]+>)?')
        type_pattern = re.compile(r'(?:export\s+)?type\s+([A-Za-z0-9_$]+)(?:<[^>]+>)?\s*=')
        func_pattern = re.compile(r'(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*(?:<[^>]+>)?\s*\(')
        const_func_pattern = re.compile(r'(?:export\s+)?(?:default\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:<[^>]+>)?\s*\(')
        const_var_pattern = re.compile(r'(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=')
        method_pattern = re.compile(r'^\s*(?:static\s+)?(?:async\s+)?([A-Za-z0-9_$]+)\s*(?:<[^>]+>)?\s*\(([^)]*)\)\s*\{')
        import_pattern = re.compile(r'import\s+(?:\{([^}]+)\}|([A-Za-z0-9_$]+))\s+from\s+[\'"]([^\'"]+)[\'"]')
        require_pattern = re.compile(r'(?:const|let|var)\s+(?:\{([^}]+)\}|([A-Za-z0-9_$]+))\s*=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)')
        exports_func_pattern = re.compile(r'(?:module\.)?exports(?:\.([A-Za-z0-9_$]+))?\s*=\s*(?:async\s*)?(?:function\s*)?(?:([A-Za-z0-9_$]+)\s*)?\(([^)]*)\)')
        in_multiline = False
        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            clean_str_line = re.sub(r"'(?:\\.|[^'\\])*'", "''", line_str)
            clean_str_line = re.sub(r'"(?:\\.|[^"\\])*"', '""', clean_str_line)
            clean_str_line = re.sub(r'`(?:\\.|[^`\\])*`', '``', clean_str_line)
            if in_multiline:
                if "*/" in clean_str_line:
                    in_multiline = False
                    line_str = line_str.split("*/", 1)[1].strip()
                else:
                    continue
            if "/*" in clean_str_line:
                if "*/" in clean_str_line:
                    line_str = re.sub(r'/\*.*?\*/', '', line_str).strip()
                else:
                    in_multiline = True
                    line_str = line_str.split("/*", 1)[0].strip()
            if not line_str or line_str.startswith("//") or line_str.startswith("*"):
                continue
            for match in class_pattern.finditer(line_str):
                name = match.group(1)
                sym_id = f"{file_path}::{name}"
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                symbols.append(Symbol(
                    id=sym_id,
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.CLASS,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"class {name}",
                    visibility=Visibility.PUBLIC if "export" in line_str else Visibility.INTERNAL,
                    modifiers=("export",) if "export" in line_str else (),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))
            for match in interface_pattern.finditer(line_str):
                name = match.group(1)
                sym_id = f"{file_path}::{name}"
                end_line = self._find_block_end(lines, idx - 1)
                loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                symbols.append(Symbol(
                    id=sym_id,
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.INTERFACE,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"interface {name}",
                    visibility=Visibility.PUBLIC if "export" in line_str else Visibility.INTERNAL,
                    modifiers=("export",) if "export" in line_str else (),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))
            for match in type_pattern.finditer(line_str):
                name = match.group(1)
                sym_id = f"{file_path}::{name}"
                loc = Location(file_path, idx, line.find(name), idx, line.find(name) + len(name))
                symbols.append(Symbol(
                    id=sym_id,
                    name=name,
                    qualified_name=name,
                    kind=SymbolKind.TYPE_ALIAS,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=f"type {name}",
                    visibility=Visibility.PUBLIC if "export" in line_str else Visibility.INTERNAL,
                    modifiers=("export",) if "export" in line_str else (),
                    content_hash=self._extract_body_hash(lines, idx - 1),
                ))
            for match in func_pattern.finditer(line_str):
                name = match.group(1)
                if name:
                    sym_id = f"{file_path}::{name}"
                    end_line = self._find_block_end(lines, idx - 1)
                    loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                    symbols.append(Symbol(
                        id=sym_id,
                        name=name,
                        qualified_name=name,
                        kind=SymbolKind.FUNCTION,
                        language=self.language,
                        location=loc,
                        parent_id=file_path,
                        signature=f"function {name}(...)",
                        visibility=Visibility.PUBLIC if "export" in line_str else Visibility.INTERNAL,
                        modifiers=("export",) if "export" in line_str else (),
                        content_hash=self._extract_body_hash(lines, idx - 1),
                    ))
            for match in const_func_pattern.finditer(line_str):
                name = match.group(1)
                if name:
                    sym_id = f"{file_path}::{name}"
                    end_line = self._find_block_end(lines, idx - 1)
                    loc = Location(file_path, idx, line.find(name), end_line, line.find(name) + len(name))
                    symbols.append(Symbol(
                        id=sym_id,
                        name=name,
                        qualified_name=name,
                        kind=SymbolKind.FUNCTION,
                        language=self.language,
                        location=loc,
                        parent_id=file_path,
                        signature=f"const {name} = (...)",
                        visibility=Visibility.PUBLIC if "export" in line_str else Visibility.INTERNAL,
                        modifiers=("export",) if "export" in line_str else (),
                        content_hash=self._extract_body_hash(lines, idx - 1),
                    ))
            for match in const_var_pattern.finditer(line_str):
                name = match.group(1)
                if name and name not in ("if", "for", "while", "switch", "catch", "function"):
                    sym_id = f"{file_path}::{name}"
                    loc = Location(file_path, idx, line.find(name), idx, line.find(name) + len(name))
                    symbols.append(Symbol(
                        id=sym_id,
                        name=name,
                        qualified_name=name,
                        kind=SymbolKind.VARIABLE,
                        language=self.language,
                        location=loc,
                        parent_id=file_path,
                        signature=f"var {name}",
                        visibility=Visibility.PUBLIC if "export" in line_str else Visibility.INTERNAL,
                        modifiers=("export",) if "export" in line_str else (),
                        content_hash=hashlib.sha256(line_str.encode()).hexdigest()[:16],
                    ))
            for match in method_pattern.finditer(line_str):
                name = match.group(1)
                params = match.group(2)
                if name not in ("if", "for", "while", "switch", "catch", "function", "constructor"):
                    sym_id = f"{file_path}::{name}"
                    loc = Location(file_path, idx, line.find(name), idx, line.find(name) + len(name))
                    symbols.append(Symbol(
                        id=sym_id,
                        name=name,
                        qualified_name=name,
                        kind=SymbolKind.METHOD,
                        language=self.language,
                        location=loc,
                        parent_id=file_path,
                        signature=f"{name}({params})",
                        visibility=Visibility.PUBLIC if "export" in line_str or "static" in line_str else Visibility.INTERNAL,
                        modifiers=("static",) if "static" in line_str else (),
                        content_hash=self._extract_body_hash(lines, idx - 1),
                    ))
            for match in import_pattern.finditer(line_str):
                spec = match.group(1) or match.group(2) or ""
                target = match.group(3)
                sym_id = f"{file_path}::import::{target}"
                loc = Location(file_path, idx, 0, idx, len(line_str))
                symbols.append(Symbol(
                    id=sym_id,
                    name=spec.strip(),
                    qualified_name=f"import:{target}",
                    kind=SymbolKind.IMPORT,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=line_str,
                    visibility=Visibility.INTERNAL,
                    modifiers=(),
                    content_hash=hashlib.sha256(line_str.encode()).hexdigest()[:16],
                ))
            for match in require_pattern.finditer(line_str):
                spec = match.group(1) or match.group(2) or ""
                target = match.group(3)
                sym_id = f"{file_path}::import::{target}"
                loc = Location(file_path, idx, 0, idx, len(line_str))
                symbols.append(Symbol(
                    id=sym_id,
                    name=spec.strip(),
                    qualified_name=f"import:{target}",
                    kind=SymbolKind.IMPORT,
                    language=self.language,
                    location=loc,
                    parent_id=file_path,
                    signature=line_str,
                    visibility=Visibility.INTERNAL,
                    modifiers=(),
                    content_hash=hashlib.sha256(line_str.encode()).hexdigest()[:16],
                ))
            for match in exports_func_pattern.finditer(line_str):
                name = match.group(1) or match.group(2)
                if name and name not in ("if", "for", "while", "switch", "catch"):
                    params = match.group(3) or ""
                    sym_id = f"{file_path}::{name}"
                    loc = Location(file_path, idx, line.find(name), idx, line.find(name) + len(name))
                    symbols.append(Symbol(
                        id=sym_id,
                        name=name,
                        qualified_name=name,
                        kind=SymbolKind.FUNCTION,
                        language=self.language,
                        location=loc,
                        parent_id=file_path,
                        signature=f"exports.{name} = ({params})",
                        visibility=Visibility.PUBLIC,
                        modifiers=("export",),
                        content_hash=self._extract_body_hash(lines, idx - 1),
                    ))
        return symbols

    def extract_edges(self, parse: ParseResult, symbols: Sequence[Symbol]) -> Iterable[Edge]:
        """Extract relationship edges for TypeScript / JavaScript AST.
        Example:
            >>> analyzer = TSLanguageAnalyzer()
            >>> res = analyzer.parse(Path("a.ts"), "import { b } from './b'; function a() { b(); }")
            >>> syms = list(analyzer.extract_symbols(res))
            >>> edges = list(analyzer.extract_edges(res, syms))
            >>> len(edges) >= 1
            True
        """
        edges: List[Edge] = []
        file_path = parse.file_path
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
            if s.kind == SymbolKind.IMPORT:
                target_mod = s.qualified_name.replace("import:", "")
                weight = float(self._count_symbol_usages(parse.source, s.name))
                edges.append(Edge(
                    source_id=file_path,
                    target_id=f"module::{target_mod}",
                    kind=EdgeKind.IMPORTS,
                    weight=weight,
                    confidence=1.0,
                    location=s.location,
                ))
        call_pattern = re.compile(r'(?<![A-Za-z0-9_$-])\b([A-Za-z_$][A-Za-z0-9_$]*)\s*\(')
        js_keywords = {
            "if", "for", "while", "switch", "catch", "function", "var", "let", "const",
            "return", "throw", "new", "typeof", "instanceof", "yield", "await", "async",
            "import", "export", "constructor", "super", "class", "case", "default",
            "else", "try", "finally", "break", "continue", "in", "of", "void", "delete", "require"
        }
        lines = parse.source.splitlines()
        func_syms = [s for s in symbols if s.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS)]
        in_multiline_edges = False
        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            clean_str_line = re.sub(r"'(?:\\.|[^'\\])*'", "''", line_str)
            clean_str_line = re.sub(r'"(?:\\.|[^"\\])*"', '""', clean_str_line)
            clean_str_line = re.sub(r'`(?:\\.|[^`\\])*`', '``', clean_str_line)
            if in_multiline_edges:
                if "*/" in clean_str_line:
                    in_multiline_edges = False
                    line_str = line_str.split("*/", 1)[1].strip()
                else:
                    continue
            if "/*" in clean_str_line:
                if "*/" in clean_str_line:
                    line_str = re.sub(r'/\*.*?\*/', '', line_str).strip()
                else:
                    in_multiline_edges = True
                    line_str = line_str.split("/*", 1)[0].strip()
            if not line_str or line_str.startswith("//") or line_str.startswith("*") or "var(" in line_str:
                continue
            enclosing = None
            for s in func_syms:
                if s.location and s.location.start_line <= idx <= (s.location.end_line or (s.location.start_line + 50)):
                    enclosing = s.id
            caller_id = enclosing or file_path
            clean_code_line = re.sub(r"'(?:\\.|[^'\\])*'", "''", line_str)
            clean_code_line = re.sub(r'"(?:\\.|[^"\\])*"', '""', clean_code_line)
            clean_code_line = re.sub(r'`(?:\\.|[^`\\])*`', '``', clean_code_line)
            clean_code_line = re.sub(r'/(?:\\.|[^/\\])+/[gimsuy]*', '//', clean_code_line)
            for match in call_pattern.finditer(clean_code_line):
                called_name = match.group(1)
                pre_str = clean_code_line[:match.start(1)].rstrip()
                is_member_call = pre_str.endswith(".") or pre_str.endswith("?.")
                if called_name[0].isupper() and not pre_str.endswith("new") and not pre_str.endswith("function"):
                    continue
                if called_name not in js_keywords and not is_member_call and called_name not in ("translateY", "translateX", "scale", "rotate"):
                    col = line.find(called_name)
                    weight = float(self._count_symbol_usages(parse.source, called_name))
                    edges.append(Edge(
                        source_id=caller_id,
                        target_id=f"{file_path}::{called_name}",
                        kind=EdgeKind.CALLS,
                        weight=weight,
                        confidence=0.75,
                        location=Location(file_path, idx, col if col >= 0 else 0, idx, col + len(called_name) if col >= 0 else len(called_name)),
                    ))
        return edges

    def _count_symbol_usages(self, source: str, symbol_name: str) -> int:
        if not symbol_name or symbol_name == "*":
            return 1
        cleaned_symbols = [s.strip() for s in symbol_name.split(",") if s.strip()]
        total = 0
        for sym in (cleaned_symbols or [symbol_name]):
            pattern = r"\b" + re.escape(sym) + r"\b"
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "export ", "//", "/*")):
                    continue
                total += len(re.findall(pattern, line))
        return max(1, total)

    def resolve_import(self, ref: ImportRef, ctx: ResolveContext) -> Iterable[str]:
        """Resolve JS/TS import reference paths via resolve_path.
        Example:
            >>> analyzer = TSLanguageAnalyzer()
            >>> ctx = ResolveContext(Path("."))
            >>> ref = ImportRef("src/a.ts", "./b", None, True)
            >>> list(analyzer.resolve_import(ref, ctx))
            []
        """
        return ctx.resolve_path(ref.file_path, ref.module_name, "typescript")
