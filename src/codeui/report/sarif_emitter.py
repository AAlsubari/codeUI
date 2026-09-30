"""SARIF 2.1.0 format report emitter."""
import json
from typing import Any, Dict
import codeui
from codeui.core.graph import Graph

class SARIFEmitter:
    """Emits OASIS SARIF v2.1.0 standard report format for CI integrations.
    Example:
        >>> g = Graph()
        >>> emitter = SARIFEmitter()
        >>> sarif = emitter.emit(g)
        >>> '$schema' in sarif
        True
    """
    def emit(self, graph: Graph) -> str:
        """Convert graph findings into SARIF v2.1.0 JSON string.
        Example:
            >>> g = Graph()
            >>> emitter = SARIFEmitter()
            >>> isinstance(emitter.emit(g), str)
            True
        """
        results = []
        for f in graph.get_findings():
            level = "error" if str(f.severity) == "error" else ("warning" if str(f.severity) == "warning" else "note")
            results.append({
                "ruleId": f.rule_id,
                "level": level,
                "message": {"text": f.message},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.location.file_id},
                        "region": {
                            "startLine": f.location.start_line,
                            "startColumn": f.location.start_col + 1,
                            "endLine": f.location.end_line,
                            "endColumn": f.location.end_col + 1,
                        },
                    }
                }],
            })
        payload = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "codeui",
                        "version": codeui.__version__,
                        "informationUri": "https://codeui.dev",
                    }
                },
                "results": results,
            }],
        }
        return json.dumps(payload, sort_keys=True, indent=2)
