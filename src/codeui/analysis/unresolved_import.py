"""Unresolved import defect analyzer."""
import json
import re
import sys
from pathlib import Path
from typing import ClassVar, Iterable, List, Set
from codeui.analysis.base import AnalysisContext, Analyzer
from codeui.core.graph import Graph
from codeui.core.ir import EdgeKind, Finding, Location, Severity

class UnresolvedImportAnalyzer(Analyzer):
    """Detects imports targeting non-existent modules or files.
    Example:
        >>> analyzer = UnresolvedImportAnalyzer()
        >>> g = Graph()
        >>> ctx = AnalysisContext(Path("."))
        >>> list(analyzer.run(g, ctx))
        []
    """
    id: ClassVar[str] = "unresolved_import"
    severity_default: ClassVar[Severity] = Severity.ERROR

    STD_MODULES: Set[str] = (
        set(getattr(sys, "stdlib_module_names", set()))
        | set(getattr(sys, "builtin_module_names", set()))
        | {
            "fs", "path", "http", "https", "os", "sys", "re", "json", "ast", "hashlib",
            "sqlite3", "math", "fmt", "io", "net", "std", "core", "alloc", "url", "events",
            "util", "stream", "buffer", "crypto", "child_process", "cluster", "dgram",
            "dns", "tls", "readline", "zlib", "codeui", "react", "react-dom", "lucide-react",
            "vite", "d3", "recharts", "motion", "clsx", "tailwind-merge", "express",
            "typing", "dataclasses", "enum", "argparse", "shutil", "tempfile", "unittest",
            "subprocess", "urllib", "concurrent", "threading", "time", "datetime", "collections",
            "itertools", "functools", "inspect", "traceback", "copy", "glob", "fnmatch",
            "typing_extensions", "pydantic", "pytest", "fastapi", "flask", "requests", "aiohttp",
            "jinja2", "yaml", "toml", "dotenv", "sync", "strings", "bytes", "context", "errors",
            "testing", "encoding", "log", "builtin", "runtime", "syscall"
        }
    )

    def run(self, graph: Graph, ctx: AnalysisContext) -> Iterable[Finding]:
        """Find unresolved import edges.
        Example:
            >>> analyzer = UnresolvedImportAnalyzer()
            >>> g = Graph()
            >>> list(analyzer.run(g, AnalysisContext(Path("."))))
            []
        """
        findings: List[Finding] = []
        all_files = set(graph.get_all_files())
        known_deps = set(self.STD_MODULES)

        for f in all_files:
            parts = f.replace("\\", "/").split("/")
            for p in parts:
                stem = p.split(".")[0]
                if stem:
                    known_deps.add(stem)
                    known_deps.add(p)

        if ctx and ctx.root_dir:
            root = ctx.root_dir
            for manifest_name in ("package.json", "requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "go.mod", "Cargo.toml"):
                mpath = root / manifest_name
                if mpath.exists():
                    try:
                        content = mpath.read_text(encoding="utf-8")
                        if manifest_name == "package.json":
                            pkg_data = json.loads(content)
                            deps = pkg_data.get("dependencies", {})
                            dev_deps = pkg_data.get("devDependencies", {})
                            known_deps.update(deps.keys())
                            known_deps.update(dev_deps.keys())
                        elif manifest_name == "requirements.txt":
                            for line in content.splitlines():
                                line = line.strip().split("#")[0].strip()
                                if line:
                                    pkg = re.split(r"[=<>!~]", line)[0].strip()
                                    if pkg:
                                        known_deps.add(pkg)
                        elif manifest_name in ("pyproject.toml", "setup.py", "Cargo.toml", "go.mod"):
                            for match in re.finditer(r'["\']([a-zA-Z0-9_-]+)["\']', content):
                                known_deps.add(match.group(1))
                    except Exception:
                        pass

        for edge in graph.get_edges():
            if edge.kind == EdgeKind.IMPORTS:
                raw_mod = edge.target_id.replace("module::", "").strip()
                if not raw_mod or raw_mod.startswith("."):
                    continue
                if raw_mod.startswith("node:"):
                    continue
                if raw_mod.startswith("@/") or raw_mod == "@":
                    base_mod = "@"
                elif raw_mod.startswith("@"):
                    base_mod = "/".join(raw_mod.split("/")[:2])
                else:
                    base_mod = raw_mod.split("/")[0].split(".")[0]

                is_known = (
                    raw_mod in known_deps
                    or base_mod in known_deps
                    or any(raw_mod in f or base_mod in f for f in all_files)
                )

                if not is_known and raw_mod.startswith("@/"):
                    as_src = "src/" + raw_mod[2:]
                    as_root = raw_mod[2:]
                    if any(as_src in f or as_root in f for f in all_files):
                        is_known = True

                if not is_known and hasattr(ctx, "resolve_path"):
                    src_file = edge.source_id.split("::")[0]
                    resolved = ctx.resolve_path(src_file, raw_mod)
                    if resolved:
                        is_known = True

                if not is_known and hasattr(ctx, "alias_mappings"):
                    for alias, target in getattr(ctx, "alias_mappings", {}).items():
                        if raw_mod.startswith(alias):
                            sub = raw_mod[len(alias):].lstrip("/")
                            target_path = Path(target) / sub
                            if target_path.exists() or any(target_path.with_suffix(ext).exists() for ext in (".ts", ".tsx", ".js", ".jsx", ".py")):
                                is_known = True
                                break

                if not is_known and ctx and ctx.root_dir:
                    candidate_rel = ctx.root_dir / raw_mod.replace(".", "/")
                    candidate_norm = ctx.root_dir / raw_mod
                    if (
                        candidate_rel.exists()
                        or candidate_norm.exists()
                        or any((candidate_rel.parent / f"{candidate_rel.name}{ext}").exists() for ext in (".ts", ".tsx", ".js", ".jsx", ".py"))
                        or any((candidate_norm.parent / f"{candidate_norm.name}{ext}").exists() for ext in (".ts", ".tsx", ".js", ".jsx", ".py"))
                        or any((candidate_rel / idx).exists() for idx in ("index.ts", "index.tsx", "index.js", "__init__.py"))
                    ):
                        is_known = True

                if not is_known:
                    loc = edge.location or Location(edge.source_id, 1, 0, 1, 0)
                    finding = Finding(
                        id=f"unresolved_import::{edge.source_id}::{raw_mod}",
                        rule_id="unresolved_import",
                        message=f"Unresolved import module '{raw_mod}'",
                        severity=self.severity_default,
                        location=loc,
                        symbol_id=edge.source_id,
                        fix_hint=f"Check import path '{raw_mod}' or install required dependency",
                        confidence=0.9,
                    )
                    findings.append(finding)
        return findings
