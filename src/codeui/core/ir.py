"""Intermediate Representation (IR) data structures for codeui."""
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict

class StrEnum(str, Enum):
    """String enum for Python 3.10+ compatibility.
    Example:
        >>> class Color(StrEnum):
        ...     RED = "red"
        >>> str(Color.RED)
        'red'
    """
    def __str__(self) -> str:
        return str(self.value)

class Visibility(StrEnum):
    """Symbol visibility scope."""
    PUBLIC = "public"
    PROTECTED = "protected"
    PRIVATE = "private"
    INTERNAL = "internal"

class LayerKind(StrEnum):
    """Architectural classification layer for files and modules.
    Example:
        >>> str(LayerKind.FRONTEND)
        'frontend'
    """
    ENTRY = "entry"
    FRONTEND = "frontend"
    BACKEND = "backend"
    HOOKS = "hooks"
    SHARED = "shared"
    TEST = "test"
    CONFIG = "config"
    OTHER = "other"

@dataclass(frozen=True, slots=True)
class FileClassification:
    """Architectural classification for a source file.
    Example:
        >>> c = FileClassification(LayerKind.FRONTEND, "auth", "components")
        >>> str(c.layer)
        'frontend'
    """
    layer: LayerKind
    feature: str
    module: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert classification to dictionary.
        Example:
            >>> c = FileClassification(LayerKind.BACKEND, "api", "server")
            >>> c.to_dict()["layer"]
            'backend'
        """
        return {
            "layer": str(self.layer),
            "feature": self.feature,
            "module": self.module,
        }

class SymbolKind(StrEnum):
    """Kind of programming symbol."""
    FILE = "file"
    MODULE = "module"
    NAMESPACE = "namespace"
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    FUNCTION = "function"
    METHOD = "method"
    PROPERTY = "property"
    VARIABLE = "variable"
    CONSTANT = "constant"
    TYPE_ALIAS = "type_alias"
    IMPORT = "import"
    EXPORT = "export"

@dataclass(frozen=True, slots=True)
class Location:
    """Source code range location.
    Example:
        >>> loc = Location("app.py", 1, 0, 10, 5)
        >>> loc.file_id
        'app.py'
    """
    file_id: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert Location to dictionary.
        Example:
            >>> loc = Location("a.py", 1, 0, 1, 10)
            >>> loc.to_dict()["file_id"]
            'a.py'
        """
        return asdict(self)

@dataclass(frozen=True, slots=True)
class Symbol:
    """Code symbol node in graph.
    Example:
        >>> loc = Location("a.py", 1, 0, 2, 0)
        >>> sym = Symbol("s1", "foo", "a.foo", SymbolKind.FUNCTION, "python", loc, None, "def foo():", Visibility.PUBLIC, (), "hash1")
        >>> sym.name
        'foo'
    """
    id: str
    name: str
    qualified_name: str
    kind: SymbolKind
    language: str
    location: Location
    parent_id: str | None
    signature: str | None
    visibility: Visibility
    modifiers: tuple[str, ...]
    content_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert Symbol to dictionary representation.
        Example:
            >>> loc = Location("a.py", 1, 0, 2, 0)
            >>> sym = Symbol("s1", "foo", "a.foo", SymbolKind.FUNCTION, "python", loc, None, "def foo():", Visibility.PUBLIC, (), "hash1")
            >>> sym.to_dict()["name"]
            'foo'
        """
        d = asdict(self)
        d["kind"] = str(self.kind)
        d["visibility"] = str(self.visibility)
        return d

class EdgeKind(StrEnum):
    """Kinds of directed relationship edges."""
    CONTAINS = "contains"
    IMPORTS = "imports"
    EXPORTS = "exports"
    CALLS = "calls"
    REFERENCES = "references"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    OVERRIDES = "overrides"
    READS = "reads"
    WRITES = "writes"
    RETURNS = "returns"
    INSTANTIATES = "instantiates"
    DEPENDS_ON = "depends_on"
    TESTS = "tests"
    DOCUMENTS = "documents"
    DUPLICATES = "duplicates"

@dataclass(frozen=True, slots=True)
class Edge:
    """Directed edge between two symbols or nodes.
    Example:
        >>> edge = Edge("s1", "s2", EdgeKind.CALLS, 1.0, 1.0, None)
        >>> edge.kind
        <EdgeKind.CALLS: 'calls'>
    """
    source_id: str
    target_id: str
    kind: EdgeKind
    weight: float
    confidence: float
    location: Location | None

    def to_dict(self) -> Dict[str, Any]:
        """Convert Edge to dictionary representation.
        Example:
            >>> edge = Edge("s1", "s2", EdgeKind.CALLS, 1.0, 1.0, None)
            >>> edge.to_dict()["kind"]
            'calls'
        """
        d = asdict(self)
        d["kind"] = str(self.kind)
        return d

class Severity(StrEnum):
    """Finding severity level."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass(frozen=True, slots=True)
class Finding:
    """Defect finding report.
    Example:
        >>> loc = Location("a.py", 1, 0, 1, 10)
        >>> f = Finding("f1", "undefined_symbol", "Symbol x undefined", Severity.ERROR, loc, "s1", "Import x or define it", 1.0)
        >>> f.rule_id
        'undefined_symbol'
    """
    id: str
    rule_id: str
    message: str
    severity: Severity
    location: Location
    symbol_id: str | None
    fix_hint: str | None
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert Finding to dictionary.
        Example:
            >>> loc = Location("a.py", 1, 0, 1, 10)
            >>> f = Finding("f1", "undefined_symbol", "Symbol x undefined", Severity.ERROR, loc, "s1", "Import x", 1.0)
            >>> f.to_dict()["severity"]
            'error'
        """
        d = asdict(self)
        d["severity"] = str(self.severity)
        return d
