"""Project structure and import reference resolution helper."""
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

class ResolveContext:
    """Context container for cross-file and cross-language import resolution.
    Example:
        >>> ctx = ResolveContext(Path("."))
        >>> isinstance(ctx.root_path, Path)
        True
    """
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path.resolve()
        self.root_dir = self.root_path
        self.alias_mappings: Dict[str, str] = {}
        self.workspace_packages: Dict[str, Path] = {}
        self.entry_points: List[str] = []
        self.layer_rules: Dict[str, Any] = {}
        self._resolve_cache: Dict[Tuple[str, str, str], List[str]] = {}
        self._known_files: Optional[Set[str]] = None
        self._search_roots: List[Path] = [self.root_path]
        self.known_extensions: Set[str] = {
            ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go",
            ".rs", ".java", ".kt", ".kts", ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
            ".cs", ".php", ".rb", ".swift", ".scala", ".sc", ".dart", ".json", ".yaml", ".yml"
        }
        self._load_configs()

    def set_supported_extensions(self, exts: Iterable[str]) -> None:
        """Configure file extensions considered during import resolution.
        Example:
            >>> ctx = ResolveContext(Path("."))
            >>> ctx.set_supported_extensions([".py", ".ts"])
        """
        self.known_extensions = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in exts}

    def set_known_files(self, files: Iterable[str]) -> None:
        """Register known project files to accelerate import resolution without disk checks.
        Example:
            >>> ctx = ResolveContext(Path("."))
            >>> ctx.set_known_files(["src/index.ts"])
            >>> ctx.has_known_file("src/index.ts")
            True
        """
        self._known_files = {f.replace("\\", "/").lstrip("./") for f in files}

    def has_known_file(self, file_path: str) -> bool:
        """Check if relative path exists in registered known files.
        Example:
            >>> ctx = ResolveContext(Path("."))
            >>> ctx.set_known_files(["a.py"])
            >>> ctx.has_known_file("a.py")
            True
        """
        if self._known_files is None:
            return (self.root_path / file_path).exists()
        return file_path.replace("\\", "/").lstrip("./") in self._known_files

    def _load_configs(self) -> None:
        """Discover tsconfig.json, package.json, codeui.json, and pyproject.toml configurations."""
        self._search_roots = [self.root_path]
        try:
            for entry in self.root_path.iterdir():
                if entry.is_dir() and not entry.name.startswith((".", "__")) and entry.name not in ("node_modules", "dist", "build", "target", "vendor", "venv", ".venv"):
                    self._search_roots.append(entry)
        except Exception:
            pass

        codeui_config = self.root_path / ".codeui.json"
        if not codeui_config.exists():
            codeui_config = self.root_path / "codeui.json"
        if codeui_config.exists():
            try:
                cdata = json.loads(codeui_config.read_text(encoding="utf-8"))
                if "entry" in cdata:
                    entries = cdata["entry"] if isinstance(cdata["entry"], list) else [cdata["entry"]]
                    self.entry_points.extend(entries)
                if "entries" in cdata:
                    self.entry_points.extend(cdata["entries"])
                if "layers" in cdata and isinstance(cdata["layers"], dict):
                    self.layer_rules.update(cdata["layers"])
            except Exception:
                pass

        tsconfig_path = self.root_path / "tsconfig.json"
        if tsconfig_path.exists():
            try:
                content = tsconfig_path.read_text(encoding="utf-8")
                data = json.loads(content)
                compiler_opts = data.get("compilerOptions", {})
                baseUrl = compiler_opts.get("baseUrl", ".")
                base_dir = (self.root_path / baseUrl).resolve()
                paths = compiler_opts.get("paths", {})
                for alias, targets in paths.items():
                    alias_clean = alias.rstrip("*").rstrip("/")
                    if targets and isinstance(targets, list):
                        target_clean = targets[0].rstrip("*").rstrip("/")
                        resolved_target = (base_dir / target_clean).resolve()
                        self.alias_mappings[alias_clean] = str(resolved_target)
            except Exception:
                pass

        package_json = self.root_path / "package.json"
        if not package_json.exists() and self.root_path.parent != self.root_path:
            parent_pkg = self.root_path.parent / "package.json"
            if parent_pkg.exists():
                package_json = parent_pkg
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                cui = data.get("codeui") or data.get("appConfig")
                if cui and isinstance(cui, dict):
                    if "entry" in cui:
                        entries = cui["entry"] if isinstance(cui["entry"], list) else [cui["entry"]]
                        self.entry_points.extend(entries)
                    if "entries" in cui:
                        self.entry_points.extend(cui["entries"])
                    if "layers" in cui and isinstance(cui["layers"], dict):
                        self.layer_rules.update(cui["layers"])
                workspaces = data.get("workspaces", [])
                if isinstance(workspaces, list):
                    for ws_pattern in workspaces:
                        ws_clean = ws_pattern.replace("/*", "")
                        ws_dir = self.root_path / ws_clean
                        if ws_dir.exists() and ws_dir.is_dir():
                            for sub in ws_dir.iterdir():
                                sub_pkg = sub / "package.json"
                                if sub_pkg.exists():
                                    sub_data = json.loads(sub_pkg.read_text(encoding="utf-8"))
                                    pkg_name = sub_data.get("name")
                                    if pkg_name:
                                        self.workspace_packages[pkg_name] = sub.resolve()
            except Exception:
                pass

    def resolve_path(self, current_file: str, import_path: str, language: str = "") -> List[str]:
        """Resolve import reference string to candidate file paths relative to root.
        Example:
            >>> ctx = ResolveContext(Path("."))
            >>> candidates = ctx.resolve_path("src/app.ts", "./utils", "typescript")
            >>> isinstance(candidates, list)
            True
        """
        cache_key = (current_file, import_path, language)
        if cache_key in self._resolve_cache:
            return self._resolve_cache[cache_key]

        all_exts = sorted(list(self.known_extensions))
        index_basenames = ["index", "__init__", "mod", "lib", "main"]

        resolved: List[str] = []
        current_dir = (self.root_path / Path(current_file).parent).resolve() if current_file else self.root_path
        clean_mod = import_path.replace("module::", "").replace("import:", "").strip()

        if clean_mod.startswith("."):
            num_dots = len(clean_mod) - len(clean_mod.lstrip("."))
            rest = clean_mod.lstrip(".")
            target_dir = current_dir
            for _ in range(num_dots - 1):
                if target_dir.parent and target_dir.parent != target_dir:
                    target_dir = target_dir.parent

            parts = [p for p in rest.replace("\\", "/").split("/") if p]
            if not parts and "." in rest:
                parts = [p for p in rest.split(".") if p]

            candidate_paths: List[Path] = []
            if not parts:
                for idx_base in index_basenames:
                    for ext in all_exts:
                        candidate_paths.append(target_dir / f"{idx_base}{ext}")
            else:
                sub_str = "/".join(parts)
                parent_sub = "/".join(parts[:-1]) if len(parts) > 1 else ""
                candidate_paths.append(target_dir / sub_str)
                for ext in all_exts:
                    candidate_paths.append(target_dir / f"{sub_str}{ext}")
                    if parent_sub:
                        candidate_paths.append(target_dir / f"{parent_sub}{ext}")
                    for idx_base in index_basenames:
                        candidate_paths.append(target_dir / sub_str / f"{idx_base}{ext}")
                        if parent_sub:
                            candidate_paths.append(target_dir / parent_sub / f"{idx_base}{ext}")

            for cp in candidate_paths:
                if self._known_files is not None:
                    try:
                        rel = str(cp.relative_to(self.root_path)).replace("\\", "/")
                        if rel in self._known_files:
                            resolved.append(rel)
                    except (ValueError, RuntimeError):
                        pass
                else:
                    if cp.exists() and cp.is_file():
                        try:
                            resolved.append(str(cp.resolve().relative_to(self.root_path)).replace("\\", "/"))
                        except (ValueError, RuntimeError):
                            pass

        for alias, target in self.alias_mappings.items():
            if import_path.startswith(alias):
                rel = import_path[len(alias):].lstrip("/")
                base = Path(target) / rel
                for ext in all_exts:
                    p = base.with_suffix(ext)
                    if self._known_files is not None:
                        try:
                            rel_p = str(p.relative_to(self.root_path)).replace("\\", "/")
                            if rel_p in self._known_files:
                                resolved.append(rel_p)
                        except (ValueError, RuntimeError):
                            pass
                    else:
                        if p.exists() and p.is_file():
                            try:
                                resolved.append(str(p.resolve().relative_to(self.root_path)).replace("\\", "/"))
                            except (ValueError, RuntimeError):
                                pass

        for pkg_name, pkg_path in self.workspace_packages.items():
            if import_path == pkg_name or import_path.startswith(pkg_name + "/"):
                rel = import_path[len(pkg_name):].lstrip("/")
                base = pkg_path / (rel if rel else "src/index.ts")
                if self._known_files is not None:
                    try:
                        rel_base = str(base.relative_to(self.root_path)).replace("\\", "/")
                        if rel_base in self._known_files:
                            resolved.append(rel_base)
                    except (ValueError, RuntimeError):
                        pass
                else:
                    if base.exists() and base.is_file():
                        try:
                            resolved.append(str(base.resolve().relative_to(self.root_path)).replace("\\", "/"))
                        except (ValueError, RuntimeError):
                            pass

        clean_mod = import_path.replace("module::", "").replace("import:", "").strip()
        if not clean_mod.startswith("."):
            mod_path_str = clean_mod.replace(".", "/")
            parts = [p for p in mod_path_str.split("/") if p]

            if self._known_files is not None:
                search_root_prefixes = [""] + [f"{r.name}/" for r in self._search_roots if r != self.root_path]
                for i in range(len(parts)):
                    sub_str = "/".join(parts[i:])
                    parent_sub = "/".join(parts[i:-1]) if len(parts[i:]) > 1 else ""
                    for prefix in search_root_prefixes:
                        for ext in all_exts:
                            cand1 = f"{prefix}{sub_str}{ext}"
                            if cand1 in self._known_files:
                                resolved.append(cand1)
                            if parent_sub:
                                cand2 = f"{prefix}{parent_sub}{ext}"
                                if cand2 in self._known_files:
                                    resolved.append(cand2)
                        for idx_base in index_basenames:
                            for ext in all_exts:
                                cand3 = f"{prefix}{sub_str}/{idx_base}{ext}"
                                if cand3 in self._known_files:
                                    resolved.append(cand3)
                                if parent_sub:
                                    cand4 = f"{prefix}{parent_sub}/{idx_base}{ext}"
                                    if cand4 in self._known_files:
                                        resolved.append(cand4)
                    if resolved:
                        break
            else:
                candidate_paths: List[Path] = []
                for i in range(len(parts)):
                    sub_parts = parts[i:]
                    sub_str = "/".join(sub_parts)
                    parent_sub = "/".join(sub_parts[:-1]) if len(sub_parts) > 1 else ""
                    for root in self._search_roots:
                        for ext in all_exts:
                            candidate_paths.append(root / f"{sub_str}{ext}")
                            if parent_sub:
                                candidate_paths.append(root / f"{parent_sub}{ext}")
                        for idx_base in index_basenames:
                            for ext in all_exts:
                                candidate_paths.append(root / sub_str / f"{idx_base}{ext}")
                                if parent_sub:
                                    candidate_paths.append(root / parent_sub / f"{idx_base}{ext}")

                for cp in candidate_paths:
                    if cp.exists() and cp.is_file():
                        try:
                            resolved.append(str(cp.resolve().relative_to(self.root_path)).replace("\\", "/"))
                        except (ValueError, RuntimeError):
                            pass

        result = list(dict.fromkeys(resolved))
        self._resolve_cache[cache_key] = result
        return result
