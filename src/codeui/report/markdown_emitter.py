"""Markdown defect report emitter."""
from typing import Any
from codeui.core.graph import Graph

class MarkdownEmitter:
    """Emits human-readable Markdown defect summary reports.
    Example:
        >>> g = Graph()
        >>> emitter = MarkdownEmitter()
        >>> report = emitter.emit(g)
        >>> '# codeui Defect Report' in report
        True
    """
    def emit(self, graph: Graph) -> str:
        """Convert graph findings to formatted Markdown document.
        Example:
            >>> g = Graph()
            >>> emitter = MarkdownEmitter()
            >>> isinstance(emitter.emit(g), str)
            True
        """
        lines = [
            "# codeui Defect Report",
            "",
            f"Total Files Analyzed: {len(graph.get_all_files())}",
            f"Total Defect Findings: {len(graph.get_findings())}",
            "",
            "| Rule ID | Severity | File | Message | Fix Hint |",
            "| --- | --- | --- | --- | --- |",
        ]
        for f in graph.get_findings():
            lines.append(f"| {f.rule_id} | {f.severity} | `{f.location.file_id}:{f.location.start_line}` | {f.message} | {f.fix_hint or '-'} |")
        return "\n".join(lines)
