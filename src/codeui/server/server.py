"""Localhost HTTP server for codeui interactive UI and REST API."""
import io
import json
import os
import re
import sys
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from codeui.core.graph import Graph
from codeui.core.ir import SymbolKind
from codeui.core.override import OverrideStore, OverrideKind
from codeui.errors import SecurityError, SymbolNotFoundError
from codeui.report.json_emitter import JSONEmitter
from codeui.report.sarif_emitter import SARIFEmitter

class CodeUIHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for codeui REST endpoints and web UI.
    Example:
        >>> handler = CodeUIHTTPRequestHandler
        >>> handler.server_version
        'BaseHTTP/0.6'
    """
    CSRF_TOKEN = "codeui-local-csrf-token"
    graph: Graph = None
    override_store: OverrideStore = None
    project_root: Path = None
    rescan_fn: Optional[Callable[..., Graph]] = None
    entry_points: Optional[List[str]] = None
    layer_rules: Optional[Dict[str, Any]] = None

    @classmethod
    def execute_rescan(cls) -> None:
        """Safely execute project rescan callback preserving entry points and layer rules."""
        fn = getattr(cls, "rescan_fn", None)
        if fn is None:
            return
        if isinstance(fn, staticmethod):
            fn = fn.__func__
        if cls.project_root:
            existing_entries = list(cls.entry_points) if cls.entry_points else (list(cls.graph._entry_points) if cls.graph and hasattr(cls.graph, "_entry_points") else None)
            existing_rules = dict(cls.layer_rules) if cls.layer_rules else (dict(cls.graph._layer_rules) if cls.graph and hasattr(cls.graph, "_layer_rules") else None)
            try:
                new_graph = fn(cls.project_root, entry_points=existing_entries, layer_rules=existing_rules)
            except TypeError:
                try:
                    new_graph = fn(cls.project_root, entry_points=existing_entries)
                except TypeError:
                    new_graph = fn(cls.project_root)
            if new_graph is not None:
                if existing_entries:
                    new_graph.set_entry_points(existing_entries)
                if existing_rules:
                    new_graph.set_layer_rules(existing_rules)
                cls.graph = new_graph

    def do_GET(self) -> None:
        """Handle GET requests for UI static assets and REST endpoints.
        Example:
            >>> handler = CodeUIHTTPRequestHandler
        """
        try:
            self._handle_get()
        except Exception as e:
            self._send_error(500, f"Internal server error: {e}")

    def _handle_get(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path in ("/", "/index.html"):
            self._serve_static_ui()
            return

        if path == "/health":
            self._send_json({"status": "ok"})
            return

        if path.startswith("/static/"):
            rel_path = path[len("/static/"):].split("?", 1)[0]
            static_root = (Path(__file__).parent / "static").resolve()
            try:
                safe_path = self._safe_rel_path(rel_path)
                if not safe_path:
                    raise SecurityError("Invalid static asset path")
                full_path = (static_root / safe_path).resolve()
                if not str(full_path).startswith(str(static_root)):
                    raise SecurityError("Asset path traversal outside static root blocked")
                if not full_path.exists() or not full_path.is_file():
                    self._send_error(404, f"Static asset not found: {rel_path}")
                    return
                data = full_path.read_bytes()
                ctype = "application/octet-stream"
                if safe_path.endswith(".css"):
                    ctype = "text/css; charset=utf-8"
                elif safe_path.endswith(".js"):
                    ctype = "application/javascript; charset=utf-8"
                elif safe_path.endswith(".html"):
                    ctype = "text/html; charset=utf-8"
                elif safe_path.endswith(".json"):
                    ctype = "application/json; charset=utf-8"
                elif safe_path.endswith(".svg"):
                    ctype = "image/svg+xml"
                elif safe_path.endswith(".png"):
                    ctype = "image/png"
                self._send_bytes(200, ctype, data)
            except SecurityError as se:
                self._send_error(403, str(se))
            except Exception as e:
                self._send_error(400, str(e))
            return

        if path.startswith("/asset/"):
            rel_path = path[len("/asset/"):].split("?", 1)[0]
            try:
                safe_path = self._safe_rel_path(rel_path)
                if not safe_path:
                    raise SecurityError("Invalid asset path")
                full_path = (self.project_root / safe_path).resolve()
                if not str(full_path).startswith(str(self.project_root.resolve())):
                    raise SecurityError("Asset path traversal outside project root blocked")
                if not full_path.exists() or not full_path.is_file():
                    self._send_error(404, f"Asset not found: {rel_path}")
                    return
                data = full_path.read_bytes()
                ctype = "application/octet-stream"
                if safe_path.endswith(".png"):
                    ctype = "image/png"
                elif safe_path.endswith((".jpg", ".jpeg")):
                    ctype = "image/jpeg"
                elif safe_path.endswith(".svg"):
                    ctype = "image/svg+xml"
                elif safe_path.endswith(".json"):
                    ctype = "application/json"
                elif safe_path.endswith(".css"):
                    ctype = "text/css"
                elif safe_path.endswith(".js"):
                    ctype = "application/javascript"
                self._send_bytes(200, ctype, data)
            except SecurityError as se:
                self._send_error(403, str(se))
            except Exception as e:
                self._send_error(400, str(e))
            return

        if path == "/api/v1/graph":
            if query.get("refresh", ["0"])[0] in ("1", "true"):
                try:
                    self.execute_rescan()
                except Exception as e:
                    self._send_error(500, f"Rescan failed: {e}")
                    return
            self._send_json(self.graph.to_dict() if self.graph else {})
            return

        if path == "/api/v1/subgraph":
            file_id = query.get("file", [""])[0] or query.get("path", [""])[0]
            symbol_id = query.get("symbol_id", [""])[0]
            if not file_id and symbol_id and "::" in symbol_id:
                file_id = symbol_id.split("::")[0]
            if not file_id and symbol_id:
                file_id = symbol_id
            if "::" in file_id:
                if not symbol_id:
                    symbol_id = file_id
                file_id = file_id.split("::")[0]
            if file_id.startswith("module::"):
                file_id = file_id[len("module::"):]
            if not file_id:
                self._send_error(400, "Parameter 'file' or 'symbol_id' is required")
                return
            try:
                raw_symbols = self.graph.get_symbols_by_file(file_id) if self.graph else []
                excluded_kinds = {SymbolKind.VARIABLE}
                symbols = [s for s in raw_symbols if s.kind not in excluded_kinds]
                cls = self.graph.get_file_classification(file_id) if self.graph else classify_file(file_id)
                sym_ids = {s.id for s in symbols}
                intra_edges = [
                    e.to_dict() for e in (self.graph.get_edges() if self.graph else [])
                    if (e.source_id in sym_ids) and (e.target_id in sym_ids)
                ]
                ext_outgoing = []
                for s_id in sym_ids:
                    for e in (self.graph.get_outgoing_edges(s_id) if self.graph else []):
                        if e.target_id not in sym_ids:
                            ext_outgoing.append(e.to_dict())
                ext_incoming = []
                for s_id in sym_ids:
                    for e in (self.graph.get_incoming_edges(s_id) if self.graph else []):
                        if e.source_id not in sym_ids:
                            ext_incoming.append(e.to_dict())
                ext_edges = ext_outgoing + ext_incoming
                related_symbols = {}
                for edge in ext_edges:
                    for endpoint_id in (edge["source_id"], edge["target_id"]):
                        if endpoint_id not in sym_ids and endpoint_id not in related_symbols:
                            if self.graph and self.graph.has_symbol(endpoint_id):
                                other_sym = self.graph.get_symbol(endpoint_id)
                                other_file = other_sym.location.file_id if other_sym.location else ""
                                other_cls = self.graph.get_file_classification(other_file) if other_file else None
                                related_symbols[endpoint_id] = {
                                    "id": other_sym.id,
                                    "name": other_sym.name,
                                    "qualified_name": other_sym.qualified_name,
                                    "kind": str(other_sym.kind),
                                    "file_id": other_file,
                                    "layer": str(other_cls.layer) if other_cls else "shared",
                                    "feature": other_cls.feature if other_cls else "external",
                                    "is_external": True,
                                    "location": other_sym.location.to_dict() if other_sym.location else None,
                                    "signature": other_sym.signature,
                                }
                            else:
                                raw_clean = endpoint_id.replace("module::", "")
                                other_file = raw_clean.split("::")[0] if "::" in raw_clean else raw_clean
                                other_name = raw_clean.split("::")[1] if "::" in raw_clean else (other_file.split("/")[-1] if "/" in other_file else other_file)
                                other_cls = self.graph.get_file_classification(other_file) if (self.graph and other_file) else None
                                related_symbols[endpoint_id] = {
                                    "id": endpoint_id,
                                    "name": other_name,
                                    "qualified_name": endpoint_id,
                                    "kind": "module" if endpoint_id.startswith("module::") else "symbol",
                                    "file_id": other_file,
                                    "layer": str(other_cls.layer) if other_cls else "shared",
                                    "feature": other_cls.feature if other_cls else "external",
                                    "is_external": True,
                                    "location": {"file_id": other_file, "start_line": 1, "end_line": 1} if other_file else None,
                                    "signature": other_name,
                                }
                self._send_json({
                    "file_id": file_id,
                    "classification": cls.to_dict(),
                    "symbols": [s.to_dict() for s in symbols],
                    "related_symbols": list(related_symbols.values()),
                    "edges": intra_edges + ext_outgoing + ext_incoming,
                })
            except Exception as e:
                self._send_error(400, str(e))
            return

        if path == "/api/v1/defects":
            findings = [f.to_dict() for f in self.graph.get_findings()] if self.graph else []
            self._send_json({"findings": findings, "count": len(findings)})
            return

        if path == "/api/v1/file":
            rel_path = query.get("path", [""])[0]
            if "::" in rel_path:
                rel_path = rel_path.split("::")[0]
            if rel_path.startswith("module::"):
                rel_path = rel_path[len("module::"):]
            try:
                content = self._read_project_file(rel_path)
                overridden_content = self.override_store.get_file_content(rel_path) if self.override_store else None
                self._send_json({"path": rel_path, "content": overridden_content if overridden_content is not None else content})
            except Exception as e:
                self._send_error(400, str(e))
            return

        if path in ("/api/v1/export", "/__export_zip__"):
            export_type = query.get("type", ["zip" if path == "/__export_zip__" else "json"])[0]
            if export_type == "diff":
                diff = self.override_store.to_diff()
                self._send_response(200, "text/plain", diff)
            elif export_type == "sarif":
                sarif = SARIFEmitter().emit(self.graph)
                self._send_response(200, "application/json", sarif)
            elif export_type == "zip":
                self._handle_zip_export()
            else:
                json_str = JSONEmitter().emit(self.graph)
                self._send_response(200, "application/json", json_str)
            return

        if path in ("/api/v1/repo/info", "/api/v1/library/repo"):
            from codeui.core.repo import get_library_repo_url
            self._send_json({
                "repo_url": get_library_repo_url(),
                "version": "0.1.0",
            })
            return

        self._send_error(404, "Endpoint Not Found")

    def _get_allowed_origin(self) -> str:
        """Derive safe CORS allowed origin restricted to local origins."""
        origin = self.headers.get("Origin", "") if self.headers else ""
        host_hdr = self.headers.get("Host", "") if self.headers else ""
        if origin:
            parsed = urllib.parse.urlparse(origin)
            if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0") or (host_hdr and parsed.netloc == host_hdr):
                return origin
        return f"http://{host_hdr}" if host_hdr else "http://127.0.0.1:3000"

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS preflight CORS requests.
        Example:
            >>> handler = CodeUIHTTPRequestHandler
        """
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self._get_allowed_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CSRF-Token")
        self.end_headers()

    def do_POST(self) -> None:
        """Handle POST requests for state overrides and edits.
        Example:
            >>> handler = CodeUIHTTPRequestHandler
        """
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/__export_zip__":
            self._handle_zip_export()
            return

        csrf_header = self.headers.get("X-CSRF-Token")
        if csrf_header != self.CSRF_TOKEN:
            self._send_error(403, "CSRF Token Validation Failed")
            return

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            self._send_error(400, "Invalid JSON payload")
            return

        if path == "/api/v1/clone":
            repo = payload.get("repo", "").strip()
            if not repo or repo.startswith("-"):
                self._send_error(400, "Parameter 'repo' is invalid")
                return
            if not repo.startswith("http://") and not repo.startswith("https://") and not repo.startswith("git@"):
                if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", repo):
                    self._send_error(400, "Invalid repository name format")
                    return
                repo_url = f"https://github.com/{repo}.git"
            else:
                if not (repo.startswith("https://") or repo.startswith("http://") or repo.startswith("git@")):
                    self._send_error(400, "Unsupported repository protocol")
                    return
                repo_url = repo
            active_dir = Path("/tmp/codeui_repos/active_repo")
            if active_dir.exists():
                import shutil
                shutil.rmtree(active_dir, ignore_errors=True)
            active_dir.parent.mkdir(parents=True, exist_ok=True)
            import subprocess
            res = subprocess.run(["git", "clone", "--depth", "1", "--", repo_url, str(active_dir)], capture_output=True, text=True)
            if res.returncode != 0:
                self._send_error(500, f"Git clone failed: {res.stderr}")
                return
            self.__class__.project_root = active_dir
            if self.override_store:
                self.override_store.revert_all()
            self.execute_rescan()
            self._send_json({
                "status": "ok",
                "repo": repo,
                "files_count": len(self.graph.get_all_files()) if self.graph else 0
            })
            return

        if path == "/api/v1/refresh":
            try:
                self.execute_rescan()
            except Exception as e:
                self._send_error(500, f"Rescan failed: {e}")
                return
            self._send_json({"status": "ok", "files_count": len(self.graph.get_all_files()) if self.graph else 0})
            return

        if path == "/api/v1/edit":
            kind = payload.get("kind", "replace_file")
            target_id = payload.get("target_id")
            new_val = payload.get("new_value", "")
            dd_raw = payload.get("direct_disk", payload.get("directDisk", payload.get("write_to_disk", payload.get("is_direct", True))))
            if isinstance(dd_raw, str):
                direct_disk = dd_raw.lower() not in ("false", "0", "no", "off")
            else:
                direct_disk = bool(dd_raw)
            if not target_id:
                self._send_error(400, "target_id is required")
                return
            if kind == "replace_file":
                full_path = self._resolve_disk_path(target_id)
                print(f"[DISK_EDIT] Request target_id='{target_id}' resolved to full_path='{full_path}' (direct_disk={direct_disk})", file=sys.stderr, flush=True)
                if not full_path:
                    print(f"[DISK_EDIT] ERROR: Could not resolve file path for target_id='{target_id}'", file=sys.stderr, flush=True)
                    self._send_error(404, f"Could not resolve file path: {target_id}")
                    return

                try:
                    rel_for_graph = str(full_path.relative_to(self.project_root.resolve())).replace("\\", "/")
                except Exception:
                    rel_for_graph = str(full_path.name)

                if direct_disk:
                    print(f"[DISK_EDIT] Attempting direct disk write to '{full_path}'...", file=sys.stderr, flush=True)
                    try:
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(new_val)
                            f.flush()
                            os.fsync(f.fileno())
                        print(f"[DISK_EDIT] SUCCESS: Direct disk write completed for '{full_path}' ({len(new_val)} bytes)", file=sys.stderr, flush=True)
                    except Exception as err:
                        print(f"[DISK_EDIT] ERROR: Direct disk write failed for '{full_path}': {err}", file=sys.stderr, flush=True)
                        self._send_error(500, f"Disk write failed for {full_path}: {err}")
                        return

                    if self.override_store:
                        self.override_store.revert(rel_for_graph)
                        self.override_store.revert(target_id)
                        clean_norm = target_id.split("::")[0].replace("module::", "").lstrip("./")
                        self.override_store.revert(clean_norm)
                    self.execute_rescan()
                    self._send_json({
                        "status": "ok",
                        "target_id": target_id,
                        "direct_disk": True,
                        "saved_path": str(full_path),
                        "relative_path": rel_for_graph,
                    })
                    return
                elif self.override_store:
                    orig_content = ""
                    try:
                        orig_content = full_path.read_text(encoding="utf-8", errors="replace") if full_path.exists() else ""
                    except Exception:
                        pass
                    self.override_store.set_file_override(
                        file_path=rel_for_graph,
                        original_content=orig_content,
                        new_content=new_val,
                        author="ui_user",
                    )
                    self._send_json({
                        "status": "ok",
                        "target_id": target_id,
                        "direct_disk": False,
                        "relative_path": rel_for_graph,
                    })
                    return

        if path == "/api/v1/revert":
            target_id = payload.get("target_id")
            if target_id == "all":
                self.override_store.revert_all()
            elif target_id:
                self.override_store.revert(target_id)
            self._send_json({"status": "ok"})
            return

        if path in ("/api/v1/agent/contribute", "/api/v1/contribute"):
            title = payload.get("title", "AI Agent Contribution")
            description = payload.get("description", "")
            file_changes = payload.get("file_changes", {})
            branch_name = payload.get("branch_name")
            token = payload.get("token")
            push = payload.get("push", True)
            try:
                from codeui.agent.contribution import ContributionManager
                mgr = ContributionManager(token=token)
                res = mgr.submit_contribution(
                    title=title,
                    description=description,
                    file_changes=file_changes,
                    branch_name=branch_name,
                    token=token,
                    push=push,
                )
                self._send_json(res)
            except Exception as e:
                self._send_error(500, f"Contribution failed: {e}")
            return

        self._send_error(404, "Endpoint Not Found")

    def _handle_zip_export(self) -> None:
        """Generate in-memory ZIP package of current project files, overrides, and metadata."""
        buf = io.BytesIO()
        written: set[str] = set()
        ignored_dirs = {"node_modules", ".venv", "dist", ".git", ".codeui", "__pycache__", ".pytest_cache"}
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in self.project_root.rglob("*"):
                if path.is_file() and path.suffix.lower() not in (".pyc", ".pyo", ".pyd") and not any(part in path.parts for part in ignored_dirs):
                    try:
                        rel = str(path.relative_to(self.project_root))
                        safe = self._safe_rel_path(rel)
                        if not safe or safe in written:
                            continue
                        overridden = self.override_store.get_file_content(safe)
                        if overridden is not None:
                            zf.writestr(safe, overridden)
                        else:
                            zf.writestr(safe, path.read_bytes())
                        written.add(safe)
                    except Exception:
                        pass
            for file_path in self.graph.get_all_files():
                safe = self._safe_rel_path(file_path)
                if not safe or safe in written:
                    continue
                overridden = self.override_store.get_file_content(file_path)
                if overridden is not None:
                    zf.writestr(safe, overridden)
                    written.add(safe)
            overrides = [o.to_dict() for o in self.override_store.list()]
            if overrides:
                zf.writestr("_overrides.json", json.dumps({"version": 1, "overrides": overrides}, indent=2))
            zf.writestr("project_full.json", json.dumps(self.graph.to_dict(), indent=2))
        buf.seek(0)
        self._send_bytes(
            200,
            "application/zip",
            buf.read(),
            {"Content-Disposition": 'attachment; filename="codeui_export.zip"'}
        )

    def _safe_rel_path(self, rel_path: str) -> Optional[str]:
        """Validate and sanitize relative path."""
        if not rel_path:
            return None
        safe = rel_path.replace("\\", "/").lstrip("/")
        parts = [p for p in safe.split("/") if p]
        if any(p == ".." for p in parts):
            return None
        return "/".join(parts)

    def _serve_static_ui(self) -> None:
        """Serve prebuilt embedded index.html visualizer asset."""
        static_dir = Path(__file__).parent / "static" / "index.html"
        if static_dir.exists():
            html_content = static_dir.read_text(encoding="utf-8")
            self._send_response(200, "text/html; charset=utf-8", html_content)
        else:
            self._send_error(500, "Static UI asset missing")

    def _resolve_disk_path(self, rel_path: str) -> Optional[Path]:
        """Resolve a relative or symbol file path to the absolute Path on disk.
        Safely locates project files across various directory layouts and prevents directory traversal.
        """
        if not rel_path or not self.project_root:
            return None
        clean_rel = rel_path.split("::")[0].replace("module::", "").replace("\\", "/").strip().lstrip("./")
        if not clean_rel:
            return None

        proj_root = self.project_root.resolve()
        proj_str = str(proj_root)

        if clean_rel.startswith(proj_str):
            clean_rel = clean_rel[len(proj_str):].lstrip("/")

        safe = self._safe_rel_path(clean_rel)
        if safe:
            cand = (proj_root / safe).resolve()
            if str(cand).startswith(proj_str) and cand.exists() and cand.is_file():
                return cand

        if safe and proj_root.name and (safe.startswith(proj_root.name + "/") or safe == proj_root.name):
            sub_safe = safe[len(proj_root.name):].lstrip("/")
            if sub_safe:
                cand = (proj_root / sub_safe).resolve()
                if str(cand).startswith(proj_str) and cand.exists() and cand.is_file():
                    return cand

        if self.graph:
            for known_file in self.graph.get_all_files():
                k_clean = known_file.replace("\\", "/").lstrip("./")
                if (k_clean == safe or
                    (safe and (k_clean.endswith("/" + safe) or safe.endswith("/" + k_clean))) or
                    (safe and Path(k_clean).name == Path(safe).name)):
                    cand = (proj_root / k_clean).resolve()
                    if str(cand).startswith(proj_str) and cand.exists() and cand.is_file():
                        return cand

        from codeui.lang.registry import LanguageRegistry
        supported_exts = LanguageRegistry().get_supported_extensions()
        if safe:
            candidates = []
            for ext in supported_exts:
                candidates.append(safe + ext)
                candidates.append(safe.replace(".", "/") + ext)
            candidates.extend([
                safe + "/index.ts",
                safe + "/index.tsx",
                safe + "/index.js",
                safe + "/index.jsx",
                safe + "/__init__.py",
                safe + "/mod.rs",
                safe + "/lib.rs",
                safe.replace(".", "/") + "/__init__.py",
            ])
            for c in candidates:
                cand = (proj_root / c).resolve()
                if str(cand).startswith(proj_str) and cand.exists() and cand.is_file():
                    return cand

        parent_root = proj_root.parent.resolve()
        if safe and parent_root != proj_root:
            cand = (parent_root / safe).resolve()
            if str(cand).startswith(str(parent_root)) and cand.exists() and cand.is_file():
                return cand

        if safe:
            cand = (proj_root / safe).resolve()
            if str(cand).startswith(proj_str):
                return cand
        return None

    def _read_project_file(self, rel_path: str) -> str:
        """Read project file safely with path traversal protection and flexible extension resolution."""
        full_path = self._resolve_disk_path(rel_path)
        if full_path and full_path.exists() and full_path.is_file():
            return full_path.read_text(encoding="utf-8", errors="replace")
        raise FileNotFoundError(f"File not found: {rel_path}")

    def _send_json(self, data: Dict[str, Any]) -> None:
        """Send JSON HTTP 200 response with security headers."""
        body = json.dumps(data, sort_keys=True, indent=2)
        self._send_response(200, "application/json; charset=utf-8", body)

    def _send_bytes(self, code: int, content_type: str, body: bytes, extra_headers: Optional[Dict[str, str]] = None) -> None:
        """Helper to send raw binary HTTP response with security headers."""
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline' data: blob:; object-src 'none'; frame-ancestors *;")
        self.send_header("Access-Control-Allow-Origin", self._get_allowed_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CSRF-Token")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_response(self, code: int, content_type: str, body: str) -> None:
        """Helper to send HTTP text response with strict CSP and security headers."""
        self._send_bytes(code, content_type, body.encode("utf-8"))

    def _send_error(self, code: int, message: str) -> None:
        """Send HTTP error payload."""
        self._send_response(code, "application/json", json.dumps({"error": message, "code": code}))

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard access logs under 400 to prevent false positive error triggers."""
        if args and len(args) > 1:
            try:
                code = int(args[1])
                if code < 400:
                    return
            except (ValueError, TypeError):
                pass
        sys.stderr.write(f"{self.address_string()} - - [{self.log_date_time_string()}] {format % args}\n")
        sys.stderr.flush()

class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

def create_server(
    graph: Graph,
    override_store: OverrideStore,
    project_root: Path,
    host: str = "127.0.0.1",
    port: int = 3000,
    rescan_fn: Optional[Callable[..., Graph]] = None,
    entry_points: Optional[Iterable[str]] = None,
    layer_rules: Optional[Dict[str, Any]] = None,
) -> ThreadingHTTPServer:
    """Instantiate and configure codeui localhost HTTP server.
    Example:
        >>> g = Graph()
        >>> store = OverrideStore()
        >>> srv = create_server(g, store, Path("."), port=0)
        >>> srv.server_port > 0
        True
        >>> srv.server_close()
    """
    CodeUIHTTPRequestHandler.graph = graph
    CodeUIHTTPRequestHandler.override_store = override_store
    CodeUIHTTPRequestHandler.project_root = project_root.resolve()
    CodeUIHTTPRequestHandler.rescan_fn = staticmethod(rescan_fn) if rescan_fn is not None else None
    if entry_points is not None:
        CodeUIHTTPRequestHandler.entry_points = list(entry_points)
    elif graph and hasattr(graph, "_entry_points") and graph._entry_points:
        CodeUIHTTPRequestHandler.entry_points = list(graph._entry_points)
    else:
        CodeUIHTTPRequestHandler.entry_points = None
    if layer_rules is not None:
        CodeUIHTTPRequestHandler.layer_rules = dict(layer_rules)
    elif graph and hasattr(graph, "_layer_rules") and graph._layer_rules:
        CodeUIHTTPRequestHandler.layer_rules = dict(graph._layer_rules)
    else:
        CodeUIHTTPRequestHandler.layer_rules = None
    return ReusableThreadingHTTPServer((host, port), CodeUIHTTPRequestHandler)
