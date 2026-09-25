"""Public API drift analyzer comparing current symbols against baseline snapshot."""
import json
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, List
from codeui.analysis.base import AnalysisContext, Analyzer
from codeui.core.graph import Graph
from codeui.core.ir import Finding, Location, Severity, Visibility

class ApiDriftAnalyzer(Analyzer):
    """Detects removed or signature-modified public symbols against prior snapshot.
    Example:
        >>> analyzer = ApiDriftAnalyzer()
        >>> g = Graph()
        >>> ctx = AnalysisContext(Path("."))
        >>> list(analyzer.run(g, ctx))
        []
    """
    id: ClassVar[str] = "api_drift"
    severity_default: ClassVar[Severity] = Severity.WARNING

    def run(self, graph: Graph, ctx: AnalysisContext) -> Iterable[Finding]:
        """Detect signature breaks in exported public API interface.
        Example:
            >>> analyzer = ApiDriftAnalyzer()
            >>> g = Graph()
            >>> list(analyzer.run(g, AnalysisContext(Path("."))))
            []
        """
        if not ctx or not ctx.root_dir:
            return []
        baseline_file = ctx.root_dir / ".codeui" / "api_baseline.json"
        if not baseline_file.exists():
            baseline_file = ctx.root_dir / "api_baseline.json"
        if not baseline_file.exists():
            return []

        try:
            baseline_data: Dict[str, Any] = json.loads(baseline_file.read_text(encoding="utf-8"))
        except Exception:
            return []

        findings: List[Finding] = []
        current_symbols = {s.id: s for s in graph.get_all_symbols()}

        for sym_id, base_info in baseline_data.items():
            if not isinstance(base_info, dict):
                continue
            name = base_info.get("name", sym_id)
            vis = base_info.get("visibility", "public")
            if vis != "public":
                continue
            base_sig = base_info.get("signature")
            if sym_id not in current_symbols:
                loc = Location(base_info.get("file_id", "api_baseline.json"), 1, 0, 1, 0)
                findings.append(Finding(
                    id=f"api_drift::removed::{sym_id}",
                    rule_id="api_drift",
                    message=f"Public API symbol '{name}' was removed from public interface",
                    severity=self.severity_default,
                    location=loc,
                    symbol_id=sym_id,
                    fix_hint=f"Restore public symbol '{name}' or update api_baseline.json",
                    confidence=0.9,
                ))
            elif base_sig:
                current_sym = current_symbols[sym_id]
                if current_sym.signature and current_sym.signature != base_sig:
                    findings.append(Finding(
                        id=f"api_drift::changed::{sym_id}",
                        rule_id="api_drift",
                        message=f"Public API signature changed for '{name}': '{current_sym.signature}' != '{base_sig}'",
                        severity=self.severity_default,
                        location=current_sym.location or Location("api_baseline.json", 1, 0, 1, 0),
                        symbol_id=sym_id,
                        fix_hint=f"Verify backward compatibility of new signature for '{name}'",
                        confidence=0.85,
                    ))

        return findings
