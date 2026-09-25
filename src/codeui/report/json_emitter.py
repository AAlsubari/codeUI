"""Deterministic JSON report emitter."""
import json
from typing import Any, Dict
from codeui.core.graph import Graph

class JSONEmitter:
    """Emits byte-identical deterministic JSON graph reports.
    Example:
        >>> g = Graph()
        >>> emitter = JSONEmitter()
        >>> report = emitter.emit(g)
        >>> '"symbols": []' in report
        True
    """
    def emit(self, graph: Graph) -> str:
        """Serialize graph to byte-identical sorted JSON string.
        Example:
            >>> g = Graph()
            >>> emitter = JSONEmitter()
            >>> isinstance(emitter.emit(g), str)
            True
        """
        data = graph.to_dict()
        return json.dumps(data, sort_keys=True, indent=2)
