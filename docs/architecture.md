# Architecture Overview

`codeui` is designed as a modular, language-agnostic static analysis engine and context builder.

Repository: [https://github.com/AAlsubari/codeUI](https://github.com/AAlsubari/codeUI)

---

## High-Level System Architecture

```
                               Source Code Base
                      (.py, .ts, .js, .go, .rs, Docker, etc.)
                                      │
                                      ▼
                           [ Language Analyzers ]
                          (codeui.lang.registry)
                                      │
                                      ▼
                     [ Intermediate Representation (IR) ]
                       (Symbol, Edge, Location, Finding)
                                      │
                                      ▼
                           [ Universal Graph Store ]
                            (codeui.core.graph.Graph)
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
 [ Defect Analyzers ]         [ Call Tracer ]            [ Context Builder ]
 (codeui.analysis.*)       (codeui.tracer.Tracer)      (codeui.agent.context)
         │                            │                            │
         └────────────────────────────┼────────────────────────────┘
                                      │
                                      ▼
                        [ Visualizer UI & Server ]
                         (codeui.server.server)
                                      │
                                      ▼
                        [ Agent Edit & Contribution ]
                      (EditTools / ContributionManager)
```

---

## Core Layers

### 1. Language Adapters (`codeui.lang.*`)
Language-specific analyzers process source text using pure static AST parsers (such as standard library `ast` for Python). Adapters extract raw symbols (functions, classes, interfaces, variables) and directed structural edges (`defines`, `calls`, `imports`, `uses`).

### 2. Universal Intermediate Representation (`codeui.core.ir`)
All entities are translated into immutable, strongly-typed IR dataclasses:
- `Symbol`: ID, kind (`Function`, `Class`, `Variable`, `Module`), visibility (`Public`, `Private`), and location.
- `Edge`: Source ID, target ID, kind (`CALLS`, `IMPORTS`, `CONTAINS`, `USES`), confidence weight.
- `Location`: File path, start line, start col, end line, end col.
- `Finding`: Rule ID, message, severity (`Error`, `Warning`, `Info`), and file location.

### 3. Graph Store & Incremental Cache (`codeui.core.graph`, `codeui.core.cache`)
`Graph` maintains adjacency lists for fast forward and backward symbol lookup. File hash-based SQLite caching (`.codeui/cache.db`) ensures incremental re-analysis skips unchanged source files.

### 4. Defect Analysis Suite (`codeui.analysis.*`)
Defect runners execute static analysis rules across the universal graph:
- Undefined identifiers & dead code detection
- Circular dependencies via Tarjan's Strongly Connected Components (SCC) algorithm
- Structural code clone detection via token shingling
- Terminal flow unreachable statement detection
- Scope variable shadowing and API drift checks

### 5. Localhost Server & Interactive UI (`codeui.server.server`)
A Python `http.server` running on `127.0.0.1` serving a Vite React force-directed graph UI. Includes CSRF token protection, CSP headers, and REST endpoints for live rescans, traces, defect reports, direct disk writes, and agent contributions.

### 6. Agent Contribution Engine (`codeui.agent.contribution`)
Handles automated repository cloning, feature branch creation, file modification, commit drafting, and GitHub pushing to `https://github.com/AAlsubari/codeUI`.
