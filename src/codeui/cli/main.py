"""Command line interface entrypoint for codeui."""
import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Union
from codeui.agent.context import ContextBuilder, TaskSpec
from codeui.analysis.base import AnalysisContext
from codeui.analysis.runner import AnalysisRunner
from codeui.core.cache import AnalysisCache
from codeui.core.graph import Graph
from codeui.core.ir import Edge, EdgeKind, Location
from codeui.core.override import Override, OverrideKind, OverrideStore
from codeui.core.repo import clone_git_repo, is_git_url
from codeui.core.resolver import ResolveContext
from codeui.lang.registry import LanguageRegistry
from codeui.report.json_emitter import JSONEmitter
from codeui.report.markdown_emitter import MarkdownEmitter
from codeui.report.sarif_emitter import SARIFEmitter
from codeui.server.server import create_server
from codeui.tracer.tracer import Tracer

def scan_project(
    project_path: Union[str, Path],
    entry_points: Optional[Sequence[str]] = None,
    layer_rules: Optional[Dict[str, Any]] = None,
    clean_cache: bool = False,
) -> Graph:
    """Scan a project directory or remote Git repository and build the universal graph.
    Example:
        >>> g = scan_project(Path("."))
        >>> isinstance(g, Graph)
        True
    """
    path_str = str(project_path)
    temp_clone_obj = None
    if is_git_url(path_str):
        resolved_project_path, temp_clone_obj = clone_git_repo(path_str)
    else:
        resolved_project_path = Path(project_path).resolve()

    cache = None
    try:
        graph = Graph()
        registry = LanguageRegistry()
        ctx = ResolveContext(resolved_project_path)
        ctx.set_supported_extensions(registry.get_all_extensions())
        cache_db_path = resolved_project_path / ".codeui" / "cache.db"
        try:
            cache = AnalysisCache(cache_db_path)
            if clean_cache:
                cache.clear()
        except Exception:
            cache = None

        all_entries: List[str] = list(ctx.entry_points)
        if entry_points:
            all_entries.extend(entry_points)
        all_rules: Dict[str, Any] = dict(ctx.layer_rules)
        if layer_rules:
            all_rules.update(layer_rules)

        if all_entries:
            graph.set_entry_points(all_entries)
        if all_rules:
            graph.set_layer_rules(all_rules)

        ignored_dir_names = {
            "node_modules", ".venv", "venv", "env", "dist", "build", ".git", ".codeui",
            "__pycache__", ".pytest_cache", ".egg-info", ".mypy_cache", ".tox", ".idea",
            ".vscode", "target", "out", "vendor", ".next", ".nuxt", "coverage", "site-packages"
        }
        ignored_exts = {
            ".pyc", ".pyo", ".pyd", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
            ".zip", ".tar", ".gz", ".lock", ".md", ".markdown", ".txt", ".rst",
            ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".map", ".log"
        }
        valid_code_exts = registry.get_supported_extensions()

        all_files: List[Path] = []
        for root, dirs, files in os.walk(resolved_project_path):
            dirs[:] = [
                d for d in dirs
                if d not in ignored_dir_names and not (d.startswith(".") and d not in (".", ".."))
            ]
            for f in files:
                p = Path(root) / f
                try:
                    resolved_p = p.resolve()
                    resolved_p.relative_to(resolved_project_path)
                except (ValueError, RuntimeError):
                    continue
                ext = p.suffix.lower()
                if ext in ignored_exts or any(p.name.endswith(e) for e in ignored_exts):
                    continue
                if ext not in valid_code_exts and p.name.lower() not in ("dockerfile", "makefile"):
                    continue
                all_files.append(p)

        if cache:
            valid_rel_paths = {
                str(p.relative_to(resolved_project_path)).replace("\\", "/")
                for p in all_files
            }
            cache.prune_stale(valid_rel_paths)

        parsed_files: Set[str] = set()
        raw_edges: List[Edge] = []
        for p in all_files:
            analyzer = registry.get_analyzer(p)
            if not getattr(analyzer, "has_ast_support", True):
                continue
            try:
                rel_path = str(p.relative_to(resolved_project_path)).replace("\\", "/")
                source = p.read_text(encoding="utf-8", errors="replace")
                content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
                cached_data = cache.get(rel_path, content_hash) if cache else None
                if cached_data is not None:
                    symbols = cache.get_symbols(rel_path, content_hash) or []
                    edges = [
                        Edge(
                            source_id=e["source_id"],
                            target_id=e["target_id"],
                            kind=EdgeKind(e["kind"]),
                            weight=e.get("weight", 1.0),
                            confidence=e.get("confidence", 1.0),
                            location=Location(
                                file_id=e["location"]["file_id"],
                                start_line=e["location"]["start_line"],
                                start_col=e["location"]["start_col"],
                                end_line=e["location"]["end_line"],
                                end_col=e["location"]["end_col"],
                            ) if e.get("location") else None,
                        )
                        for e in cached_data.get("edges", [])
                    ]
                else:
                    parse_res = analyzer.parse(Path(rel_path), source)
                    symbols = list(analyzer.extract_symbols(parse_res))
                    edges = list(analyzer.extract_edges(parse_res, symbols))
                    if cache:
                        cache.put(rel_path, content_hash, {
                            "symbols": [s.to_dict() for s in symbols],
                            "edges": [e.to_dict() for e in edges],
                        })
                for s in symbols:
                    graph.add_symbol(s)
                for e in edges:
                    graph.add_edge(e)
                    raw_edges.append(e)
                parsed_files.add(rel_path)
            except Exception as ex:
                logging.warning(f"Error analyzing {p}: {ex}")

        ctx.set_known_files(parsed_files)

        for edge in raw_edges:
            if edge.kind == EdgeKind.CONTAINS:
                continue
            src_file = edge.source_id.split("::")[0]
            target_raw = edge.target_id.replace("module::", "").replace("import:", "").strip()
            target_file_cand = target_raw.split("::")[0]
            target_sym_name = target_raw.split("::")[1] if "::" in target_raw else (target_raw.split(".")[-1] if "." in target_raw else "")

            if not (target_file_cand.startswith(".") or "/" in target_file_cand or "." in target_file_cand or edge.kind == EdgeKind.IMPORTS or target_file_cand in parsed_files):
                continue

            resolved_targets = ctx.resolve_path(src_file, target_file_cand)
            if not resolved_targets and not target_file_cand.startswith("."):
                dot_candidates = ctx.resolve_path(src_file, f"./{target_file_cand}")
                if dot_candidates:
                    resolved_targets = dot_candidates

            for rt in resolved_targets:
                if rt != src_file and rt in parsed_files:
                    file_edge = Edge(
                        source_id=src_file,
                        target_id=rt,
                        kind=edge.kind if edge.kind != EdgeKind.CONTAINS else EdgeKind.IMPORTS,
                        weight=edge.weight,
                        confidence=edge.confidence,
                        location=edge.location,
                    )
                    graph.add_edge(file_edge)
                    if target_sym_name:
                        cand_sym_id = f"{rt}::{target_sym_name}"
                        if graph.has_symbol(cand_sym_id):
                            graph.add_edge(Edge(
                                source_id=edge.source_id,
                                target_id=cand_sym_id,
                                kind=edge.kind,
                                weight=edge.weight,
                                confidence=edge.confidence,
                                location=edge.location,
                            ))

        runner = AnalysisRunner()
        actx = AnalysisContext(root_dir=resolved_project_path, resolve_context=ctx)
        runner.run_all(graph, ctx=actx)
        return graph
    finally:
        if cache:
            cache.close()
        if temp_clone_obj:
            temp_clone_obj.cleanup()

def export_pages(
    project_path: Union[str, Path] = ".",
    out_dir: Union[str, Path] = "dist",
    entry_points: Optional[Sequence[str]] = None,
    clean_cache: bool = False,
) -> Path:
    """Export static code graph and report artifacts for standalone browser preview.
    Example:
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as td:
        ...     out = export_pages(Path("."), Path(td) / "dist")
        ...     out.exists()
        True
    """
    resolved_proj = Path(project_path).resolve()
    resolved_out = Path(out_dir).resolve()
    resolved_out.mkdir(parents=True, exist_ok=True)

    g = scan_project(resolved_proj, entry_points=entry_points, clean_cache=clean_cache)

    (resolved_out / "graph.json").write_text(JSONEmitter().emit(g), encoding="utf-8")

    ctx = AnalysisContext(resolved_proj)
    findings = [f.to_dict() for f in AnalysisRunner().run_all(g, ctx)]
    (resolved_out / "defects.json").write_text(
        json.dumps({"findings": findings, "count": len(findings)}, indent=2),
        encoding="utf-8",
    )

    static_src = Path(__file__).resolve().parent.parent / "server" / "static"
    if static_src.exists():
        static_out = resolved_out / "static"
        static_out.mkdir(parents=True, exist_ok=True)
        for item in static_src.rglob("*"):
            if item.is_file() and item.name != "index.html":
                rel = item.relative_to(static_src)
                dest = static_out / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(item.read_bytes())

        index_src = static_src / "index.html"
        if index_src.exists():
            html_text = index_src.read_text(encoding="utf-8")
            html_text = html_text.replace('href="/static/', 'href="static/')
            html_text = html_text.replace('src="/static/', 'src="static/')
            (resolved_out / "index.html").write_text(html_text, encoding="utf-8")

    (resolved_out / ".nojekyll").touch(exist_ok=True)
    return resolved_out

def main(args: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint.
    Example:
        >>> main(["langs", "--json"]) # doctest: +ELLIPSIS
        {...}
        0
    """
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    parser = argparse.ArgumentParser(prog="codeui", description="Universal code-intelligence engine", parents=[parent_parser])
    subparsers = parser.add_subparsers(dest="command")

    init_p = subparsers.add_parser("init", parents=[parent_parser], help="Initialize .codeui workspace directory")
    init_p.add_argument("project", nargs="?", default=".", help="Project path")

    scan_p = subparsers.add_parser("scan", parents=[parent_parser], help="Scan project and build code graph")
    scan_p.add_argument("project", nargs="?", default=".", help="Project path")
    scan_p.add_argument("--entry", action="append", help="Explicit application entry point(s)")
    scan_p.add_argument("--out", default=".codeui", help="Output cache directory")
    scan_p.add_argument("--clean-cache", action="store_true", help="Clear stale cache before scanning")

    pages_p = subparsers.add_parser("pages", parents=[parent_parser], help="Export static interactive graph and report artifacts")
    pages_p.add_argument("project", nargs="?", default=".", help="Project path")
    pages_p.add_argument("--out", default="dist", help="Output directory for static artifacts (default: dist)")
    pages_p.add_argument("--entry", action="append", help="Explicit application entry point(s)")
    pages_p.add_argument("--clean-cache", action="store_true", help="Clear stale cache before exporting")

    serve_p = subparsers.add_parser("serve", parents=[parent_parser], help="Start localhost web UI server")
    serve_p.add_argument("project", nargs="?", default=".", help="Project path")
    serve_p.add_argument("--entry", action="append", help="Explicit application entry point(s)")
    serve_p.add_argument("--host", default="127.0.0.1", help="Host interface to bind to (e.g. 127.0.0.1 or 0.0.0.0)")
    serve_p.add_argument("--port", type=int, default=3000, help="Port number")

    trace_p = subparsers.add_parser("trace", parents=[parent_parser], help="Trace symbol logic")
    trace_p.add_argument("symbol", help="Target symbol ID")
    trace_p.add_argument("project", nargs="?", default=".", help="Project path")
    trace_p.add_argument("--direction", choices=["forward", "backward"], default="forward")
    trace_p.add_argument("--depth", type=int, default=5)

    context_p = subparsers.add_parser("context", parents=[parent_parser], help="Build dynamic AI agent context bundle")
    context_p.add_argument("project", nargs="?", default=".", help="Project path")
    context_p.add_argument("--symbol", help="Target symbol ID")
    context_p.add_argument("--file", help="Target file ID")
    context_p.add_argument("--query", default="Analyze code", help="Task query description")
    context_p.add_argument("--defect", help="Target defect finding ID")
    context_p.add_argument("--depth", type=int, default=1)

    diff_p = subparsers.add_parser("diff", parents=[parent_parser], help="Display unified diff of active session overrides")
    diff_p.add_argument("--overrides", default=".codeui/overrides.json", help="Path to overrides.json file")

    apply_p = subparsers.add_parser("apply", parents=[parent_parser], help="Apply file edits directly to project files on disk")
    apply_p.add_argument("file", help="Target file path to edit")
    apply_p.add_argument("--content", help="New content to write to file")
    apply_p.add_argument("--from-file", help="Path to source file containing new content")
    apply_p.add_argument("--project", default=".", help="Project root directory")
    apply_p.add_argument("--disk", action="store_true", default=True, help="Write directly to project file on disk (default)")
    apply_p.add_argument("--no-disk", action="store_false", dest="disk", help="Store only in overrides without mutating disk")

    defects_p = subparsers.add_parser("defects", parents=[parent_parser], help="List defect findings")
    defects_p.add_argument("project", nargs="?", default=".", help="Project path")
    defects_p.add_argument("--severity", choices=["error", "warning", "info"])
    defects_p.add_argument("--format", choices=["json", "sarif", "markdown"], default="json")

    subparsers.add_parser("langs", parents=[parent_parser], help="List supported programming languages")
    subparsers.add_parser("plugins", parents=[parent_parser], help="List loaded plugins")
    subparsers.add_parser("repo", parents=[parent_parser], help="Display official codeui GitHub repository URL")

    contrib_p = subparsers.add_parser("contribute", parents=[parent_parser], help="Clone codeui, apply modifications, and push contribution to GitHub")
    contrib_p.add_argument("--title", required=True, help="Contribution or bug fix title")
    contrib_p.add_argument("--description", default="", help="Detailed description of the change")
    contrib_p.add_argument("--file", action="append", nargs=2, metavar=("PATH", "CONTENT"), help="File relative path and new content")
    contrib_p.add_argument("--branch", help="Target git branch name")
    contrib_p.add_argument("--token", help="GitHub authentication token")
    contrib_p.add_argument("--no-push", action="store_false", dest="push", help="Commit locally without pushing to GitHub")

    parsed = parser.parse_args(args)

    if parsed.command == "init":
        p = Path(parsed.project).resolve()
        (p / ".codeui").mkdir(parents=True, exist_ok=True)
        if parsed.json:
            print(json.dumps({"status": "initialized", "dir": str(p / ".codeui")}))
        else:
            print(f"Initialized .codeui workspace directory in {p}")
        return 0
    elif parsed.command == "scan":
        p = Path(parsed.project).resolve()
        g = scan_project(p, entry_points=parsed.entry, clean_cache=parsed.clean_cache)
        out_dir = Path(parsed.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "graph.json").write_text(JSONEmitter().emit(g), encoding="utf-8")
        if parsed.json:
            print(JSONEmitter().emit(g))
        else:
            print(f"Scanned {len(g.get_all_files())} files, {len(g.get_all_symbols())} symbols, {len(g.get_findings())} defects.")
        return 0
    elif parsed.command == "pages":
        out_path = export_pages(
            project_path=parsed.project,
            out_dir=parsed.out,
            entry_points=parsed.entry,
            clean_cache=parsed.clean_cache,
        )
        if parsed.json:
            print(json.dumps({"status": "exported", "out_dir": str(out_path)}))
        else:
            print(f"Exported static graph and report artifacts to '{out_path}'.")
        return 0
    elif parsed.command == "serve":
        p = Path(parsed.project).resolve()
        g = scan_project(p, entry_points=parsed.entry)
        store = OverrideStore()
        try:
            server = create_server(g, store, p, host=parsed.host, port=parsed.port, rescan_fn=scan_project, entry_points=parsed.entry)
        except OSError as e:
            if "already in use" in str(e).lower() or getattr(e, "errno", 0) == 98:
                try:
                    import subprocess
                    subprocess.run(["fuser", "-k", f"{parsed.port}/tcp"], capture_output=True)
                except Exception:
                    pass
                server = create_server(g, store, p, host=parsed.host, port=parsed.port, rescan_fn=scan_project, entry_points=parsed.entry)
            else:
                raise
        print(f"codeui UI server running on http://{parsed.host}:{parsed.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
        return 0
    elif parsed.command == "trace":
        p = Path(parsed.project).resolve()
        g = scan_project(p)
        tracer = Tracer(g)
        results = []
        if parsed.direction == "forward":
            results = list(tracer.forward(parsed.symbol, depth=parsed.depth))
        else:
            results = list(tracer.backward(parsed.symbol, depth=parsed.depth))
        if parsed.json:
            print(json.dumps([s.to_dict() for s in results], sort_keys=True, indent=2))
        else:
            print(f"Trace {parsed.direction} for {parsed.symbol} ({len(results)} symbols found):")
            for sym in results:
                print(f"  - {sym.kind} {sym.id} ({sym.location.file_id}:{sym.location.start_line})")
        return 0
    elif parsed.command == "context":
        p = Path(parsed.project).resolve()
        g = scan_project(p)
        builder = ContextBuilder(g)
        if parsed.defect:
            bundle = builder.for_defect(parsed.defect)
        elif parsed.symbol:
            bundle = builder.for_symbol(parsed.symbol, depth=parsed.depth)
        elif parsed.file:
            bundle = builder.for_file(parsed.file, depth=parsed.depth)
        else:
            task = TaskSpec(query=parsed.query, target_symbols=[s for s in [parsed.symbol] if s], target_files=[f for f in [parsed.file] if f])
            bundle = builder.for_task(task, depth=parsed.depth)
        print(bundle.to_json())
        return 0
    elif parsed.command == "diff":
        store = OverrideStore()
        overrides_path = Path(parsed.overrides)
        if overrides_path.exists():
            try:
                data = json.loads(overrides_path.read_text(encoding="utf-8"))
                items = data if isinstance(data, list) else data.get("overrides", [])
                for item in items:
                    if item.get("kind") == "replace_file":
                        store.set_file_override(
                            file_path=item["target_id"],
                            original_content=item.get("original_content", ""),
                            new_content=item.get("new_value", ""),
                            author=item.get("author", "user"),
                            note=item.get("note"),
                        )
            except Exception as ex:
                logging.warning(f"Error loading overrides from {overrides_path}: {ex}")
        diff_text = store.to_diff()
        if parsed.json:
            print(json.dumps({"diff": diff_text, "overrides_count": len(list(store.list()))}))
        else:
            if diff_text:
                print(diff_text)
            else:
                print("No active file differences in overrides.")
        return 0
    elif parsed.command == "apply":
        proj_path = Path(parsed.project).resolve()
        new_content = parsed.content
        if new_content is None and parsed.from_file:
            new_content = Path(parsed.from_file).read_text(encoding="utf-8")
        if new_content is None:
            new_content = sys.stdin.read()
        g = Graph()
        store = OverrideStore()
        from codeui.agent.edit_tools import EditTools
        tools = EditTools(g, store, project_root=proj_path, direct_disk=parsed.disk)
        prop = tools.replace_file(parsed.file, new_content)
        if parsed.disk:
            saved_path = tools.apply_to_disk(prop)
            if parsed.json:
                print(json.dumps({"status": "written_to_disk", "file": parsed.file, "path": str(saved_path)}))
            else:
                print(f"Applied changes directly to file on disk: {saved_path}")
        else:
            tools.apply(prop, write_to_disk=False)
            if parsed.json:
                print(json.dumps({"status": "stored_override", "file": parsed.file}))
            else:
                print(f"Stored non-destructive override for: {parsed.file}")
        return 0
    elif parsed.command == "langs":
        langs = LanguageRegistry().supported_languages()
        if parsed.json:
            print(json.dumps({"languages": langs}))
        else:
            print("Supported languages: " + ", ".join(langs))
        return 0
    elif parsed.command == "defects":
        p = Path(parsed.project).resolve()
        g = scan_project(p)
        if parsed.format == "sarif":
            print(SARIFEmitter().emit(g))
        elif parsed.format == "markdown":
            print(MarkdownEmitter().emit(g))
        else:
            print(JSONEmitter().emit(g))
        return 0
    elif parsed.command == "plugins":
        if parsed.json:
            print(json.dumps({"plugins": []}))
        else:
            print("Loaded plugins: none")
        return 0
    elif parsed.command == "repo":
        from codeui.core.repo import get_library_repo_url
        repo_url = get_library_repo_url()
        if parsed.json:
            print(json.dumps({"repo_url": repo_url}))
        else:
            print(f"codeui GitHub Repository: {repo_url}")
        return 0
    elif parsed.command == "contribute":
        from codeui.agent.contribution import ContributionManager
        changes = {f[0]: f[1] for f in (parsed.file or [])}
        mgr = ContributionManager(token=parsed.token)
        res = mgr.submit_contribution(
            title=parsed.title,
            description=parsed.description,
            file_changes=changes,
            branch_name=parsed.branch,
            token=parsed.token,
            push=parsed.push,
        )
        if parsed.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Contribution status: {res['status']}")
            print(f"Target Branch: {res['branch']}")
            print(f"Repository: {res['repo_url']}")
            if res.get("changed_files"):
                print("Changed files: " + ", ".join(res["changed_files"]))
        return 0

    parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main())
