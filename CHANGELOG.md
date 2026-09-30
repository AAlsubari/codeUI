# CHANGELOG — codeui

## [0.1.1] - 2026-09-29
### Changed
- Standardized packaging exclusively on `pyproject.toml` (PEP 517/PEP 621), eliminating redundant and conflicting `setup.py`.
- Synchronized package version to `0.1.1` across `pyproject.toml`, `codeui.__version__`, SARIF report emitter, REST API metadata, and `package.json`.
- Enhanced interactive graph canvas with dynamic physics spacing, hierarchical symbols clustering, and centralized theme token support.
- Streamlined defect-to-symbol navigation linking defect cards directly to isolated symbol subgraphs and error highlights in code editor.

## [0.1.0] - 2026-09-19
### Added
- Initial release of `codeui`.
- Frozen Core Intermediate Representation (`Location`, `Symbol`, `SymbolKind`, `Visibility`, `EdgeKind`, `Edge`, `Finding`, `Severity`).
- Language adapters for TypeScript/JavaScript, Python, Go, Rust, and generic markup/config files.
- 8 core defect analyzers (`undefined`, `dead_code`, `unresolved_import`, `circular`, `duplicates`, `unreachable`, `shadowing`, `api_drift`).
- In-memory non-destructive `OverrideStore` supporting live edits, unified diff generation, and patch exports.
- Localhost HTTP UI server bound to `127.0.0.1` serving prebuilt Canvas 2D graph visualizer.
- AI Agent Context Builder with graph traversal bundling and dry-run proposal tools.
- CLI subcommands (`scan`, `serve`, `trace`, `defects`, `context`, `diff`, `langs`, `plugins`).
