/**
 * Primary Application Controller orchestrating CodeUI interactive explorer.
 */
class App {
    static async init() {
        if (window.ThemeManager) {
            window.ThemeManager.init();
        }
        if (window.Sidebar) {
            window.Sidebar.init();
        }
        window.mainCanvas = new GraphCanvas("graph-canvas", true);
        this.setupKeyboardShortcuts();
        this.setupGlobalClickListener();

        const urlParams = new URLSearchParams(window.location.search);
        const repoParam = urlParams.get("repo") || urlParams.get("repository");
        if (repoParam) {
            const input = document.getElementById("clone-repo-input");
            if (input) input.value = repoParam;
            await this.cloneRepository(repoParam);
            return;
        }

        await this.loadData();
    }

    static showLoading(isLoading, text = "Processing...") {
        const overlay = document.getElementById("canvas-loading-overlay");
        const txt = document.getElementById("loading-overlay-text");
        if (overlay) {
            overlay.style.display = isLoading ? "flex" : "none";
            if (txt && text) txt.textContent = text;
        }
    }

    static async loadData(forceRefresh = false) {
        try {
            this.showLoading(true, "Loading universal code graph...");
            const graphData = await CodeUIAPI.getGraph(forceRefresh);
            appState.rawGraph = graphData;

            const defectsRes = await CodeUIAPI.getDefects();
            appState.defectsData = defectsRes.findings || [];

            this.initSymbolFilters();
            this.applyGraphFilter();
            Sidebar.renderCurrentTab();
        } catch (e) {
            this.showToast(`Failed to load graph: ${e.message}`, "error");
        } finally {
            this.showLoading(false);
        }
    }

    static async cloneRepository(repoOverride = null) {
        const input = document.getElementById("clone-repo-input");
        const btn = document.getElementById("btn-clone-repo");
        const repo = (repoOverride || input?.value || "").trim();
        if (!repo) {
            this.showToast("Please enter a GitHub repository name (e.g. expressjs/express) or Git URL", "error");
            return;
        }

        if (btn) {
            btn.disabled = true;
            btn.textContent = "Loading...";
        }

        this.showToast(`Loading repository ${repo}...`, "info");
        this.showLoading(true, `Loading repository ${repo}...`);
        try {
            const res = await CodeUIAPI.cloneRepo(repo);
            if (res.graph) {
                appState.rawGraph = res.graph;
                appState.defectsData = [];
                this.initSymbolFilters();
                this.applyGraphFilter();
                Sidebar.renderCurrentTab();
            } else {
                await this.loadData(false);
            }
            this.showToast(`Successfully loaded ${repo} (${res.files_count} files)`, "success");
            if (input && !repoOverride) input.value = "";
        } catch (e) {
            this.showToast(`Failed to load repository: ${e.message}`, "error");
        } finally {
            this.showLoading(false);
            if (btn) {
                btn.disabled = false;
                btn.textContent = "Clone";
            }
        }
    }

    static switchGraphMode(mode) {
        appState.graphMode = mode;
        document.getElementById("btn-mode-files")?.classList.toggle("active", mode === "files");
        document.getElementById("btn-mode-symbols")?.classList.toggle("active", mode === "symbols");
        this.renderSymbolFilterPopover();
        this.applyGraphFilter();
    }

    static getDiscoveredSymbolKinds() {
        if (!appState.rawGraph || !Array.isArray(appState.rawGraph.symbols)) {
            return [];
        }
        const counts = new Map();
        for (const s of appState.rawGraph.symbols) {
            if (!s || s.kind === "file") continue;
            const k = String(s.kind || "other").toLowerCase();
            counts.set(k, (counts.get(k) || 0) + 1);
        }
        return Array.from(counts.entries())
            .map(([kind, count]) => ({ kind, count }))
            .sort((a, b) => b.count - a.count || a.kind.localeCompare(b.kind));
    }

    static initSymbolFilters() {
        if (!appState.symbolKindFilters) {
            appState.symbolKindFilters = {};
        }
        const discovered = this.getDiscoveredSymbolKinds();
        discovered.forEach(({ kind }) => {
            if (appState.symbolKindFilters[kind] === undefined) {
                appState.symbolKindFilters[kind] = (kind !== "variable" && kind !== "var");
            }
        });
        this.renderSymbolFilterPopover();
    }

    static renderSymbolFilterPopover() {
        const container = document.getElementById("symbol-filter-items-container");
        if (!container) return;

        const discovered = this.getDiscoveredSymbolKinds();
        if (discovered.length === 0) {
            container.innerHTML = `<div style="font-size:0.72rem; color:var(--text-dim); text-align:center; padding:8px;">No symbol categories discovered</div>`;
            return;
        }

        const formatLabel = (k) => {
            const pretty = k.replace(/_/g, " ");
            return pretty.charAt(0).toUpperCase() + pretty.slice(1);
        };

        container.innerHTML = discovered.map(({ kind, count }) => {
            const isChecked = appState.symbolKindFilters?.[kind] !== false;
            const safeKind = kind.replace(/[^a-zA-Z0-9_-]/g, "");
            return `
                <div class="symbol-filter-item" onclick="App.toggleSymbolFilter('${safeKind}')">
                    <label onclick="event.stopPropagation()">
                        <input type="checkbox" id="filter-dyn-${safeKind}" ${isChecked ? "checked" : ""} onchange="App.toggleSymbolFilter('${safeKind}')">
                        <span class="badge ${safeKind}" style="font-size:0.65rem; padding:1px 5px;">${formatLabel(kind)}</span>
                    </label>
                    <span class="symbol-filter-count">${count}</span>
                </div>
            `;
        }).join("");

        const filterBtn = document.getElementById("btn-toggle-symbol-filter-popover");
        if (filterBtn) {
            const hasDisabled = discovered.some(({ kind }) => appState.symbolKindFilters?.[kind] === false);
            filterBtn.classList.toggle("active", hasDisabled);
        }
    }

    static toggleSymbolFilter(kind) {
        if (!appState.symbolKindFilters) {
            appState.symbolKindFilters = {};
        }
        const current = appState.symbolKindFilters[kind] !== false;
        appState.symbolKindFilters[kind] = !current;
        this.renderSymbolFilterPopover();
        this.applyGraphFilter();
        if (window.mainCanvas) {
            window.mainCanvas.alpha = Math.max(window.mainCanvas.alpha || 0, 0.65);
        }
    }

    static setAllSymbolFilters(enableAll) {
        if (!appState.symbolKindFilters) {
            appState.symbolKindFilters = {};
        }
        const discovered = this.getDiscoveredSymbolKinds();
        discovered.forEach(({ kind }) => {
            appState.symbolKindFilters[kind] = !!enableAll;
        });
        this.renderSymbolFilterPopover();
        this.applyGraphFilter();
        if (window.mainCanvas) {
            window.mainCanvas.alpha = Math.max(window.mainCanvas.alpha || 0, 0.65);
        }
    }

    static toggleSymbolFilterPopover() {
        const popover = document.getElementById("symbol-filter-popover");
        if (!popover) return;
        const isHidden = popover.style.display === "none" || !popover.style.display;
        if (isHidden) {
            this.renderSymbolFilterPopover();
            popover.style.display = "block";
        } else {
            popover.style.display = "none";
        }
    }

    static closeSymbolFilterPopover() {
        const popover = document.getElementById("symbol-filter-popover");
        if (popover) {
            popover.style.display = "none";
        }
    }

    static switchColorMode(mode) {
        appState.colorMode = mode;
        window.mainCanvas?.render();
        Sidebar.renderCurrentTab();
    }

    static switchLayoutMode(mode) {
        appState.layoutMode = mode;
        const select = document.getElementById("select-layout-mode");
        if (select) select.value = mode;
        window.mainCanvas?.setLayout(mode);
    }

    static switchTheme(theme) {
        if (window.ThemeManager) {
            window.ThemeManager.applyTheme(theme);
        } else {
            appState.theme = theme;
            document.body.setAttribute("data-theme", theme);
            const select = document.getElementById("select-theme");
            if (select) select.value = theme;
            window.mainCanvas?.render();
            if (window.mainCanvas?.miniMap) window.mainCanvas.miniMap.update();
        }
    }

    static toggleUnusedHighlight() {
        appState.unusedHighlightMode = !appState.unusedHighlightMode;
        const btn = document.getElementById("btn-toggle-unused");
        if (btn) {
            btn.textContent = appState.unusedHighlightMode ? "⚠️ Unused: ON" : "⚠️ Unused: OFF";
            btn.classList.toggle("active", appState.unusedHighlightMode);
        }
        window.mainCanvas?.render();
        if (window.mainCanvas?.miniMap) {
            window.mainCanvas.miniMap.update();
        }
    }

    static toggleDirectDiskEdit() {
        this.setDirectDiskEdit(!appState.directDiskWrite);
    }

    static setDirectDiskEdit(isEnabled) {
        appState.directDiskWrite = !!isEnabled;
        const btn = document.getElementById("btn-toggle-direct-disk");
        if (btn) {
            btn.textContent = appState.directDiskWrite ? "💾 Disk Edit: ON" : "💾 Disk Edit: OFF";
            btn.classList.toggle("active", appState.directDiskWrite);
            btn.classList.toggle("success", appState.directDiskWrite);
        }
        // Update all open subgraph editor toggle checkboxes/badges if present
        document.querySelectorAll(".subgraph-toggle-disk-input").forEach(inp => {
            inp.checked = appState.directDiskWrite;
        });
        const msg = appState.directDiskWrite
            ? "Direct disk edit enabled: modifications will write directly to project files on disk"
            : "In-memory override mode enabled: modifications are saved non-destructively in session store";
        this.showToast(msg, appState.directDiskWrite ? "warning" : "info");
    }

    static showApiDriftPanel() {
        if (Sidebar.collapsed) {
            Sidebar.toggleSidebar();
        }
        Sidebar.switchTab("defects");
        Sidebar.setDefectSubFilter("api_drift");
        const count = (appState.defectsData || []).filter(d => d.rule_id === "api_drift").length;
        if (count > 0) {
            this.showToast(`Detected ${count} API Drift warnings against baseline snapshot`, "warning");
        } else {
            this.showToast("No API Drift detected (symbols match API baseline)", "info");
        }
    }

    static async setApiBaseline() {
        try {
            this.showToast("Creating Public API Baseline snapshot...", "info");
            const res = await CodeUIAPI.setApiBaseline();
            this.showToast(`API Baseline created for ${res.baseline_count} public symbols`, "success");
            await this.loadData(false);
            if (Sidebar.collapsed) {
                Sidebar.toggleSidebar();
            }
            Sidebar.switchTab("defects");
            Sidebar.setDefectSubFilter("api_drift");
        } catch (e) {
            this.showToast(`Failed to set API baseline: ${e.message}`, "error");
        }
    }

    static toggleClusterHulls() {
        appState.clusterHullsMode = !appState.clusterHullsMode;
        window.mainCanvas?.render();
    }

    static toggleSim() {
        if (!window.mainCanvas) return;
        window.mainCanvas.isRunning = !window.mainCanvas.isRunning;
        const btn = document.getElementById("btn-pause-sim");
        if (btn) btn.textContent = window.mainCanvas.isRunning ? "Pause" : "Resume";
    }

    static reheatSim() {
        if (!window.mainCanvas) return;
        window.mainCanvas.alpha = 1.0;
        window.mainCanvas.isRunning = true;
        const btn = document.getElementById("btn-pause-sim");
        if (btn) btn.textContent = "Pause";
    }

    static filterGraph(query) {
        appState.searchQuery = query.toLowerCase();
        this.applyGraphFilter();
        Sidebar.renderCurrentTab();
    }

    static applyGraphFilter() {
        if (!appState.rawGraph || !window.mainCanvas) return;
        const filesInfo = appState.rawGraph.files_info || {};
        const query = appState.searchQuery;

        if (appState.graphMode === "files") {
            const allFiles = appState.rawGraph.files || [];
            const files = allFiles.filter(f => {
                const info = filesInfo[f] || {};
                if (appState.activeLayerFilter !== "all" && info.layer !== appState.activeLayerFilter) return false;
                if (query && !f.toLowerCase().includes(query)) return false;
                return true;
            });

            const validFileSet = new Set(files);
            const allFileSet = new Set(allFiles);

            // Universal file path resolver for intra/inter-module links
            const resolveFile = (id, fromFile = null) => {
                if (!id) return null;
                if (validFileSet.has(id)) return id;

                // Handle symbol ID with ::
                const filePart = id.split("::")[0].replace(/^module::/, "");
                if (validFileSet.has(filePart)) return filePart;

                // Clean relative paths
                const clean = filePart.replace(/^\.\//, "");
                if (validFileSet.has(clean)) return clean;

                // Match exact file without extension in valid files
                for (const f of validFileSet) {
                    const fNoExt = f.replace(/\.[^/.]+$/, "");
                    if (f === clean || fNoExt === clean) {
                        return f;
                    }
                }

                // Match dotted imports or normalized slash paths
                const slashed = clean.replace(/\./g, "/");
                for (const f of validFileSet) {
                    const fClean = f.replace(/\.[^/.]+$/, "");
                    if (f === slashed || fClean === slashed || f.endsWith("/" + slashed) || fClean.endsWith("/" + slashed)) {
                        return f;
                    }
                    if (f.endsWith("/" + slashed + "/index") || fClean.endsWith("/" + slashed + "/index") || f.endsWith("/" + slashed + "/__init__") || fClean.endsWith("/" + slashed + "/__init__")) {
                        return f;
                    }
                }

                // Relative path resolution from source file directory
                if (fromFile && (clean.startsWith("./") || clean.startsWith("../") || !clean.includes("/"))) {
                    const fromDir = fromFile.includes("/") ? fromFile.substring(0, fromFile.lastIndexOf("/")) : "";
                    const candidate = fromDir ? `${fromDir}/${clean.replace(/^\.\//, "")}` : clean.replace(/^\.\//, "");
                    if (validFileSet.has(candidate)) return candidate;
                    for (const f of validFileSet) {
                        const fNoExt = f.replace(/\.[^/.]+$/, "");
                        if (fNoExt === candidate || fNoExt === candidate + "/index" || fNoExt === candidate + "/__init__") {
                            return f;
                        }
                    }
                }

                // Match by file stem/name fallback
                const stem = clean.split("/").pop().split(".")[0];
                if (stem && stem.length > 2) {
                    for (const f of validFileSet) {
                        const fName = f.split("/").pop().split(".")[0];
                        if (fName === stem) return f;
                    }
                }

                return null;
            };

            const nodes = files.map(f => {
                const info = filesInfo[f] || {};
                return {
                    id: f,
                    label: f.split("/").pop(),
                    layer: info.layer || "other",
                    feature: info.feature || "root",
                    radius: info.layer === "entry" ? 10 : 8
                };
            });

            const linkMap = new Map();
            (appState.rawGraph.edges || []).forEach(e => {
                if (e.kind === "contains") return;
                const srcFile = resolveFile(e.source_id);
                const tgtFile = resolveFile(e.target_id, srcFile);
                if (srcFile && tgtFile && srcFile !== tgtFile) {
                    const linkKey = `${srcFile}-->${tgtFile}`;
                    if (linkMap.has(linkKey)) {
                        const existing = linkMap.get(linkKey);
                        existing.weight += (e.weight || 1);
                    } else {
                        linkMap.set(linkKey, {
                            source: srcFile,
                            target: tgtFile,
                            kind: e.kind || "imports",
                            weight: e.weight || 1
                        });
                    }
                }
            });

            const links = Array.from(linkMap.values());
            window.mainCanvas.setData(nodes, links);
        } else {
            const isKindActive = (k) => {
                if (!k) return false;
                const kind = String(k).toLowerCase();
                if (appState.symbolKindFilters && appState.symbolKindFilters[kind] !== undefined) {
                    return !!appState.symbolKindFilters[kind];
                }
                return true;
            };

            const nodes = [];
            const filesWithSymbols = new Set();

            (appState.rawGraph.symbols || []).forEach(s => {
                if (s.kind === "file") return;
                if (!isKindActive(s.kind)) return;
                if (query && !s.name.toLowerCase().includes(query) && !s.qualified_name?.toLowerCase().includes(query)) {
                    return;
                }

                const fileId = s.location?.file_id || "";
                if (fileId) filesWithSymbols.add(fileId);

                const fileMeta = filesInfo[fileId] || {};
                const cleanPath = fileId.replace(/\\/g, "/").replace(/^\.\//, "");
                const parts = cleanPath.split("/").filter(Boolean);
                const folder = fileMeta.folder || (parts.length > 1 ? parts.slice(0, -1).join("/") : "root");
                const mainFolder = fileMeta.main_folder || (parts.length > 1 ? parts[0] : "root");
                const subfolder = fileMeta.subfolder || (parts.length > 2 ? parts[parts.length - 2] : (parts.length > 1 ? parts[0] : "root"));

                nodes.push({
                    id: s.id,
                    label: s.name,
                    kind: s.kind,
                    type: "symbol",
                    fileId: fileId,
                    folder: folder,
                    mainFolder: mainFolder,
                    subfolder: subfolder,
                    layer: fileMeta.layer || "shared",
                    feature: fileMeta.feature || s.kind,
                    rawSymbol: s,
                    radius: s.kind === "class" ? 11 : (s.kind === "function" ? 9 : (s.kind === "method" ? 7 : (s.kind === "variable" ? 5 : 8)))
                });
            });

            // Add lone file nodes ONLY for files that have 0 detected symbols
            (appState.rawGraph.files || []).forEach(file => {
                const fileInfo = filesInfo[file] || {};
                const symCount = typeof fileInfo.symbol_count === "number" ? fileInfo.symbol_count : 0;
                if (!filesWithSymbols.has(file) && symCount === 0) {
                    if (query && !file.toLowerCase().includes(query)) return;
                    const cleanPath = file.replace(/\\/g, "/").replace(/^\.\//, "");
                    const parts = cleanPath.split("/").filter(Boolean);
                    const folder = fileInfo.folder || (parts.length > 1 ? parts.slice(0, -1).join("/") : "root");
                    const mainFolder = fileInfo.main_folder || (parts.length > 1 ? parts[0] : "root");
                    const subfolder = fileInfo.subfolder || (parts.length > 2 ? parts[parts.length - 2] : (parts.length > 1 ? parts[0] : "root"));

                    nodes.push({
                        id: file,
                        label: file.split("/").pop(),
                        kind: "file",
                        type: "file",
                        fileId: file,
                        folder: folder,
                        mainFolder: mainFolder,
                        subfolder: subfolder,
                        layer: fileInfo.layer || "other",
                        feature: fileInfo.feature || "root",
                        radius: 12,
                        isLoneFile: true
                    });
                }
            });

            const activeNodeIds = new Set(nodes.map(n => n.id));
            const links = [];
            (appState.rawGraph.edges || []).forEach(e => {
                if (activeNodeIds.has(e.source_id) && activeNodeIds.has(e.target_id) && e.source_id !== e.target_id) {
                    links.push({
                        source: e.source_id,
                        target: e.target_id,
                        kind: e.kind || "calls",
                        weight: e.weight || 1
                    });
                }
            });

            window.mainCanvas.setData(nodes, links);
        }
    }

    static togglePathTracer() {
        appState.tracerActive = !appState.tracerActive;
        const btn = document.getElementById("btn-path-tracer");
        if (btn) btn.classList.toggle("active", appState.tracerActive);

        if (appState.tracerActive) {
            appState.traceStartNode = null;
            appState.traceEndNode = null;
            appState.activeTracePath = [];
            appState.currentTraceHopIdx = 0;
            this.updateTracerHUD();
            this.showToast("Path Tracer Active: Click Source node on canvas", "info");
        } else {
            this.clearTracer();
        }
    }

    static handleTracerNodeClick(nodeId) {
        if (!appState.tracerActive || !nodeId) return;
        if (!appState.traceStartNode) {
            appState.traceStartNode = nodeId;
            appState.traceEndNode = null;
            appState.activeTracePath = [];
            appState.currentTraceHopIdx = 0;
            this.showToast(`Tracer Source: ${nodeId.split("/").pop()}. Now click Target node`, "info");
        } else if (!appState.traceEndNode) {
            if (appState.traceStartNode === nodeId) {
                this.showToast(`Selected node is already the source. Please choose a different target node`, "info");
                return;
            }
            appState.traceEndNode = nodeId;
            appState.currentTraceHopIdx = 0;
            this.computeAndHighlightPath(appState.traceStartNode, appState.traceEndNode);
        } else {
            if (appState.traceStartNode === nodeId) {
                this.showToast(`Source is already ${nodeId.split("/").pop()}. Click a different node to trace`, "info");
                return;
            }
            if (appState.traceEndNode === nodeId) {
                return;
            }
            appState.traceStartNode = nodeId;
            appState.traceEndNode = null;
            appState.activeTracePath = [];
            appState.currentTraceHopIdx = 0;
            this.showToast(`Tracer Reset: Source is now ${nodeId.split("/").pop()}. Click Target`, "info");
        }
        this.updateTracerHUD();
        window.mainCanvas?.render();
    }

    static computeAndHighlightPath(startId, endId) {
        if (!window.mainCanvas) return;
        const adj = new Map();
        window.mainCanvas.links.forEach(l => {
            const s = typeof l.source === "object" ? l.source.id : l.source;
            const t = typeof l.target === "object" ? l.target.id : l.target;
            if (!adj.has(s)) adj.set(s, []);
            adj.get(s).push(t);
        });

        const queue = [[startId]];
        const visited = new Set([startId]);
        let foundPath = null;

        while (queue.length > 0) {
            const path = queue.shift();
            const curr = path[path.length - 1];
            if (curr === endId) {
                foundPath = path;
                break;
            }
            const neighbors = adj.get(curr) || [];
            for (let next of neighbors) {
                if (!visited.has(next)) {
                    visited.add(next);
                    queue.push([...path, next]);
                }
            }
        }

        if (foundPath) {
            appState.activeTracePath = foundPath;
            appState.currentTraceHopIdx = 0;
            this.showToast(`Found dependency path: ${foundPath.length - 1} hops!`, "success");
        } else {
            appState.activeTracePath = [];
            this.showToast("No direct directed path found between nodes", "error");
        }
        this.updateTracerHUD();
        window.mainCanvas.render();
    }

    static tracerStepPrev() {
        if (!appState.activeTracePath || appState.activeTracePath.length === 0) return;
        appState.currentTraceHopIdx = Math.max(0, (appState.currentTraceHopIdx || 0) - 1);
        const nodeId = appState.activeTracePath[appState.currentTraceHopIdx];
        const node = (window.mainCanvas?.nodes || []).find(n => n.id === nodeId);
        if (node && window.mainCanvas) {
            window.mainCanvas.smoothPanZoomTo(node.x, node.y, 1.8);
        }
        this.updateTracerHUD();
    }

    static tracerStepNext() {
        if (!appState.activeTracePath || appState.activeTracePath.length === 0) return;
        appState.currentTraceHopIdx = Math.min(appState.activeTracePath.length - 1, (appState.currentTraceHopIdx || 0) + 1);
        const nodeId = appState.activeTracePath[appState.currentTraceHopIdx];
        const node = (window.mainCanvas?.nodes || []).find(n => n.id === nodeId);
        if (node && window.mainCanvas) {
            window.mainCanvas.smoothPanZoomTo(node.x, node.y, 1.8);
        }
        this.updateTracerHUD();
    }

    static clearTracer() {
        appState.tracerActive = false;
        appState.traceStartNode = null;
        appState.traceEndNode = null;
        appState.activeTracePath = [];
        appState.currentTraceHopIdx = 0;
        const btn = document.getElementById("btn-path-tracer");
        if (btn) btn.classList.remove("active");
        this.hideNodeHUD();
        window.mainCanvas?.render();
    }

    static updateTracerHUD() {
        if (!appState.tracerActive) {
            this.hideNodeHUD();
            return;
        }

        let hud = document.getElementById("node-hud-panel");
        if (!hud) {
            hud = document.createElement("div");
            hud.id = "node-hud-panel";
            hud.className = "node-hud-panel";
            document.getElementById("canvas-container")?.appendChild(hud);
        }

        const srcName = appState.traceStartNode ? appState.traceStartNode.split("/").pop() : "Click node...";
        const tgtName = appState.traceEndNode ? appState.traceEndNode.split("/").pop() : (appState.traceStartNode ? "Click target node..." : "Pending");
        const path = appState.activeTracePath || [];
        const hopsCount = path.length > 1 ? `${path.length - 1} Hops Found` : (appState.traceEndNode ? "No direct path" : "Waiting for endpoints");

        let pathListHtml = "";
        if (path.length > 0) {
            pathListHtml = path.map((id, idx) => {
                const name = id.split("/").pop();
                const isCurrent = idx === (appState.currentTraceHopIdx || 0);
                return `<span class="hop-chip ${isCurrent ? 'active' : ''}">${idx + 1}. ${name}</span>`;
            }).join(" <span class='hop-arrow'>➔</span> ");
        }

        hud.innerHTML = `
            <div class="hud-header">
                <span class="hud-tracer-title">⚡ Path Tracer Control</span>
                <button class="secondary btn-close-hud" onclick="App.clearTracer()" title="Exit Tracer">✕</button>
            </div>
            <div class="hud-tracer-flow">
                <div class="tracer-endpoint source" title="${appState.traceStartNode || ''}">
                    <span class="endpoint-label">SOURCE</span>
                    <span class="endpoint-val">${srcName}</span>
                </div>
                <div class="tracer-arrow">➔</div>
                <div class="tracer-endpoint target" title="${appState.traceEndNode || ''}">
                    <span class="endpoint-label">TARGET</span>
                    <span class="endpoint-val">${tgtName}</span>
                </div>
            </div>
            ${path.length > 0 ? `
            <div class="hud-tracer-results">
                <div class="tracer-hops-count">${hopsCount} (Step ${(appState.currentTraceHopIdx || 0) + 1}/${path.length})</div>
                <div class="tracer-hops-list">${pathListHtml}</div>
            </div>
            <div class="hud-actions">
                <button class="secondary" onclick="App.tracerStepPrev()">◀ Prev Hop</button>
                <button class="secondary" onclick="App.tracerStepNext()">Next Hop ▶</button>
                <button class="danger" onclick="App.clearTracer()">Reset</button>
            </div>
            ` : `
            <div class="hud-tracer-results">
                <div style="color:var(--text-muted); font-size:0.72rem;">
                    ${appState.traceStartNode ? 'Now click a target node to find the dependency path.' : 'Click any node on the graph to set the source.'}
                </div>
            </div>
            <div class="hud-actions">
                <button class="danger" onclick="App.clearTracer()">Close</button>
            </div>
            `}
        `;
        hud.style.display = "block";
    }

    static showNodeHUD(node, force = false) {
        if (!appState.tracerActive) {
            this.hideNodeHUD();
            return;
        }
        this.updateTracerHUD();
    }

    static hideNodeHUD(explicitClose = false) {
        if (explicitClose) {
            appState.hudExplicitlyClosed = true;
        }
        const hud = document.getElementById("node-hud-panel");
        if (hud) hud.style.display = "none";
    }

    // --- Quick Command Palette (Cmd / Ctrl + K) ---
    static openQuickPalette() {
        let palette = document.getElementById("quick-palette-modal");
        if (!palette) {
            palette = document.createElement("div");
            palette.id = "quick-palette-modal";
            palette.className = "palette-modal-backdrop";
            palette.innerHTML = `
                <div class="palette-modal-card">
                    <div class="palette-input-wrapper">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                        <input type="text" id="palette-search-input" placeholder="Search files, symbols, defects..." autocomplete="off">
                        <kbd class="kbd-badge">ESC</kbd>
                    </div>
                    <div class="palette-results" id="palette-results-list"></div>
                </div>
            `;
            document.body.appendChild(palette);

            palette.addEventListener("click", e => {
                if (e.target === palette) this.closeQuickPalette();
            });

            const input = document.getElementById("palette-search-input");
            input?.addEventListener("input", () => this.filterPaletteResults(input.value));
            input?.addEventListener("keydown", e => this.handlePaletteKeyNav(e));
        }

        palette.style.display = "flex";
        const input = document.getElementById("palette-search-input");
        if (input) {
            input.value = "";
            input.focus();
            this.filterPaletteResults("");
        }
    }

    static closeQuickPalette() {
        const palette = document.getElementById("quick-palette-modal");
        if (palette) palette.style.display = "none";
    }

    static filterPaletteResults(query) {
        const resultsEl = document.getElementById("palette-results-list");
        if (!resultsEl) return;
        const q = (query || "").toLowerCase();

        const files = (appState.rawGraph.files || []).filter(f => f.toLowerCase().includes(q)).slice(0, 8);
        const symbols = (appState.rawGraph.symbols || []).filter(s => s.name.toLowerCase().includes(q) || s.qualified_name.toLowerCase().includes(q)).slice(0, 8);
        const defects = (appState.defectsData || []).filter(d => d.rule_id.toLowerCase().includes(q) || d.message.toLowerCase().includes(q)).slice(0, 6);

        let html = "";
        if (files.length > 0) {
            html += `<div class="palette-group-title">Project Files</div>`;
            files.forEach((f, idx) => {
                html += `
                    <div class="palette-item ${idx === 0 ? 'selected' : ''}" data-type="file" data-id="${f}" onclick="App.selectPaletteItem('file', '${f}')">
                        <span>📄 ${f.split('/').pop()}</span>
                        <span style="font-size:0.68rem; color:var(--text-dim);">${f}</span>
                    </div>
                `;
            });
        }

        if (symbols.length > 0) {
            html += `<div class="palette-group-title">Symbols & Functions</div>`;
            symbols.forEach(s => {
                html += `
                    <div class="palette-item" data-type="symbol" data-id="${s.id}" data-file="${s.id.split('::')[0]}" onclick="App.selectPaletteItem('symbol', '${s.id}')">
                        <span>⚡ ${s.name}</span>
                        <span class="badge ${s.kind}">${s.kind}</span>
                    </div>
                `;
            });
        }

        if (defects.length > 0) {
            html += `<div class="palette-group-title">Defect Findings</div>`;
            defects.forEach(d => {
                const fId = d.location?.file_id || "unknown";
                html += `
                    <div class="palette-item" data-type="defect" data-id="${d.id}" data-file="${fId}" data-line="${d.location?.start_line || 1}" onclick="App.selectPaletteItem('defect', '${fId}', ${d.location?.start_line || 1})">
                        <span style="color:var(--danger);">⚠️ ${d.rule_id}</span>
                        <span style="font-size:0.68rem; color:var(--text-muted);">${d.message.slice(0, 45)}...</span>
                    </div>
                `;
            });
        }

        if (!html) {
            html = `<div style="padding:20px; text-align:center; color:var(--text-dim); font-size:0.75rem;">No matching files, symbols, or findings found.</div>`;
        }
        resultsEl.innerHTML = html;
    }

    static handlePaletteKeyNav(e) {
        if (e.key === "Escape") {
            this.closeQuickPalette();
            return;
        }
        const items = document.querySelectorAll(".palette-item");
        if (items.length === 0) return;
        let selectedIdx = Array.from(items).findIndex(i => i.classList.contains("selected"));

        if (e.key === "ArrowDown") {
            e.preventDefault();
            items[selectedIdx]?.classList.remove("selected");
            selectedIdx = (selectedIdx + 1) % items.length;
            items[selectedIdx]?.classList.add("selected");
            items[selectedIdx]?.scrollIntoView({ block: "nearest" });
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            items[selectedIdx]?.classList.remove("selected");
            selectedIdx = (selectedIdx - 1 + items.length) % items.length;
            items[selectedIdx]?.classList.add("selected");
            items[selectedIdx]?.scrollIntoView({ block: "nearest" });
        } else if (e.key === "Enter") {
            e.preventDefault();
            const cur = items[selectedIdx] || items[0];
            if (cur) {
                const type = cur.getAttribute("data-type");
                const id = cur.getAttribute("data-id");
                const line = cur.getAttribute("data-line");
                this.selectPaletteItem(type, id, line);
            }
        }
    }

    static selectPaletteItem(type, id, line = 1) {
        this.closeQuickPalette();
        if (type === "file") {
            Sidebar.onFileCardClick(id);
        } else if (type === "symbol") {
            const fileId = id.split("::")[0];
            SubGraphManager.openWindow(fileId, id);
        } else if (type === "defect") {
            Sidebar.openDefectLocation(id, line, null, "");
        }
    }

    // --- Keyboard Shortcuts ---
    static setupKeyboardShortcuts() {
        window.addEventListener("keydown", e => {
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
                if (e.key === "Escape") {
                    this.closeQuickPalette();
                    this.hideShortcutsModal();
                }
                return;
            }

            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                this.openQuickPalette();
                return;
            }

            if (e.key === "f" || e.key === "F") {
                window.mainCanvas?.fitToScreen();
            } else if (e.key === " ") {
                e.preventDefault();
                this.toggleSim();
            } else if (e.key === "l" || e.key === "L") {
                const layouts = ["force", "hierarchical", "radial", "clusters"];
                const next = layouts[(layouts.indexOf(appState.layoutMode) + 1) % layouts.length];
                this.switchLayoutMode(next);
            } else if (e.key === "t" || e.key === "T") {
                const themeKeys = window.ThemeManager ? Object.keys(window.ThemeManager.themes) : ["dark", "cyber", "light", "forest", "monokai"];
                const currentIndex = Math.max(0, themeKeys.indexOf(appState.theme));
                const next = themeKeys[(currentIndex + 1) % themeKeys.length];
                this.switchTheme(next);
                this.showToast(`Theme: ${window.ThemeManager?.getTheme(next)?.name || next}`, "info");
            } else if (e.key === "1") {
                Sidebar.switchTab("files");
            } else if (e.key === "2") {
                Sidebar.switchTab("features");
            } else if (e.key === "3") {
                Sidebar.switchTab("defects");
            } else if (e.key === "4") {
                Sidebar.switchTab("stats");
            } else if (e.key === "?") {
                this.toggleShortcutsModal();
            } else if (e.key === "Escape") {
                this.closeQuickPalette();
                this.hideShortcutsModal();
                this.closeSymbolFilterPopover();
                this.clearTracer();
                this.hideNodeHUD();
                window.mainCanvas?.clearNeighborhoodIsolation();
            }
        });
    }

    static toggleShortcutsModal() {
        let modal = document.getElementById("shortcuts-modal");
        if (!modal) {
            modal = document.createElement("div");
            modal.id = "shortcuts-modal";
            modal.className = "palette-modal-backdrop";
            modal.innerHTML = `
                <div class="palette-modal-card" style="max-width:440px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <span style="font-weight:700; font-size:0.9rem; color:var(--text-main);">Keyboard Shortcuts</span>
                        <button class="secondary" onclick="App.hideShortcutsModal()">✕</button>
                    </div>
                    <div class="shortcuts-grid">
                        <div class="shortcut-row"><span>Quick Find & Jump</span><kbd>⌘K / Ctrl+K</kbd></div>
                        <div class="shortcut-row"><span>Fit / Center Canvas</span><kbd>F</kbd></div>
                        <div class="shortcut-row"><span>Pause / Resume Physics</span><kbd>Space</kbd></div>
                        <div class="shortcut-row"><span>Cycle Layout Modes</span><kbd>L</kbd></div>
                        <div class="shortcut-row"><span>Cycle Color Themes</span><kbd>T</kbd></div>
                        <div class="shortcut-row"><span>Sidebar Tabs 1–4</span><kbd>1 · 2 · 3 · 4</kbd></div>
                        <div class="shortcut-row"><span>Clear / Close Modals</span><kbd>Esc</kbd></div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            modal.addEventListener("click", e => {
                if (e.target === modal) this.hideShortcutsModal();
            });
        }
        modal.style.display = modal.style.display === "flex" ? "none" : "flex";
    }

    static hideShortcutsModal() {
        const modal = document.getElementById("shortcuts-modal");
        if (modal) modal.style.display = "none";
    }

    static exportZip() {
        CodeUIAPI.exportZip();
    }

    static setupGlobalClickListener() {
        document.addEventListener("click", e => {
            const isInsideFilter = e.target.closest("#symbol-filter-popover, #btn-toggle-symbol-filter-popover");
            if (!isInsideFilter) {
                App.closeSymbolFilterPopover();
            }

            if (e.target.closest("button, select, input, textarea, a, .palette-modal-card, .minimap-container, .sim-controls, .zoom-controls, .shortcuts-grid, .symbol-filter-popover")) {
                return;
            }
            if (e.target.tagName !== "CANVAS") {
                if (appState.selectedFileNodeId || appState.focusedNeighborhood) {
                    window.mainCanvas?.clearNeighborhoodIsolation();
                    Sidebar.clearSelection();
                    if (!appState.tracerActive) {
                        App.hideNodeHUD();
                    }
                }
            }
        });
    }

    static toggleHeaderCompact() {
        const header = document.querySelector("header");
        const btn = document.getElementById("btn-toggle-header-compact");
        const icon = document.getElementById("header-toggle-icon");
        if (!header) return;

        const isCompact = header.classList.toggle("compact-header");

        if (btn) {
            btn.title = isCompact
                ? "Show Header Controls & Settings"
                : "Toggle Fullscreen Graph Mode (Hide Header Controls)";
            btn.classList.toggle("active", isCompact);
        }

        if (icon) {
            icon.innerHTML = isCompact
                ? '<path d="m6 9 6 6 6-6"/>'
                : '<path d="m18 15-6-6-6 6"/>';
        }

        setTimeout(() => {
            window.dispatchEvent(new Event("resize"));
            if (window.mainCanvas) {
                window.mainCanvas.setupCanvas();
            }
        }, 50);
    }

    static showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        if (!container) return;
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(-10px)";
            setTimeout(() => toast.remove(), 300);
        }, 3200);
    }
}

window.App = App;
window.addEventListener("DOMContentLoaded", () => App.init());
