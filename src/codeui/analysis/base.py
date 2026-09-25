"""Base class and context for defect analyzers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, Optional
from codeui.core.graph import Graph
from codeui.core.ir import Finding, Severity

@dataclass
class AnalysisContext:
    """Execution context for analyzers.
    Example:
        >>> ctx = AnalysisContext(Path("."))
        >>> ctx.root_dir
        PosixPath('.')
    """
    root_dir: Path
    config: Dict[str, Any] = None
    resolve_context: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = {}

class Analyzer(ABC):
    """Abstract base class for static analysis rules.
    Example:
        >>> class MockAnalyzer(Analyzer):
        ...     id = "mock"
        ...     severity_default = Severity.WARNING
        ...     def run(self, graph, ctx): return []
        >>> a = MockAnalyzer()
        >>> a.id
        'mock'
    """
    id: ClassVar[str]
    severity_default: ClassVar[Severity]

    @abstractmethod
    def run(self, graph: Graph, ctx: AnalysisContext) -> Iterable[Finding]:
        """Run analysis on the graph and yield findings."""
        pass
