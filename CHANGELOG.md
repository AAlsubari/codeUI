# CHANGELOG — codeui

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
