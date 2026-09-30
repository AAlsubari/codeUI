class SubGraphWindow {
    constructor(fileId, targetSymbolId = null, targetLine = null, targetMessage = "", initialOffset = 30, initialTab = "graph") {
        let clean = (fileId || "").replace(/^module::/, "").replace(/^\.\//, "").trim();
        let symId = targetSymbolId;
        if (clean.includes("::")) {
            const parts = clean.split("::");
            clean = parts[0];
            if (!symId) symId = fileId;
        }
        this.fileId = clean;
        this.targetSymbolId = symId;
        this.targetLine = targetLine;
        this.targetMessage = targetMessage;
        this.initialTab = initialTab;
        this.winId = `subgraph-win-${this.fileId.replace(/[^a-zA-Z0-9]/g, "_")}`;
        this.data = null;
        this.fileContent = "";
        this.canvasInstance = null;
        this.offset = initialOffset;
        this.showCrossUsage = false;
        this.moveMode = false;
        this.createDOM();
        this.loadData();
    }

    createDOM() {
        const existing = document.getElementById(this.winId);
        if (existing) {
            existing.remove();
        }

        const container = document.getElementById("canvas-container");
        const win = document.createElement("div");
        win.className = "subgraph-window";
        win.id = this.winId;
        win.style.left = `${this.offset}px`;
        win.style.top = `${this.offset}px`;

        const filename = this.fileId.split("/").pop();

        win.innerHTML = `
            <div class="subgraph-window-header" id="${this.winId}-header">
                <div class="subgraph-window-title" title="${this.fileId}">
                    <span>📄</span>
                    <span class="subgraph-header-path" id="${this.winId}-header-path">${this.fileId}</span>
                </div>
                <div class="subgraph-nav">
                    <button class="subtab-btn active" onclick="SubGraphManager.switchTab('${this.fileId}', 'graph')">Symbols Graph</button>
                    <button class="subtab-btn" onclick="SubGraphManager.switchTab('${this.fileId}', 'usages')">Cross Usages</button>
                    <button class="subtab-btn" onclick="SubGraphManager.switchTab('${this.fileId}', 'code')">Code Editor</button>
                </div>
                <div class="subgraph-window-actions">
                    <button class="btn-move-window secondary" id="${this.winId}-move-btn" onclick="SubGraphManager.toggleMoveMode('${this.fileId}')" title="Toggle Move Mode to Drag Window" style="cursor:pointer; padding:2px 8px; font-weight:700;">✥ Move</button>
                    <button class="secondary" onclick="SubGraphManager.minimizeWindow('${this.fileId}')">_</button>
                    <button class="secondary" onclick="SubGraphManager.maximizeWindow('${this.fileId}')">⛶</button>
                    <button class="danger" onclick="SubGraphManager.closeWindow('${this.fileId}')">✕</button>
                </div>
            </div>

            <div class="subgraph-panel active" id="${this.winId}-panel-graph" style="position:relative;">
                <div class="subgraph-top-controls" style="position:absolute; top:8px; left:8px; z-index:15; display:flex; gap:6px; align-items:center;">
                    <button class="secondary" id="${this.winId}-btn-cross" onclick="SubGraphManager.toggleCrossUsage('${this.fileId}')" title="Toggle Related & Cross Usages" style="font-size:0.7rem; padding:2px 7px; font-weight:600; background:var(--bg-surface); border:1px solid var(--border-subtle); backdrop-filter:blur(6px);">🌐 Cross</button>
                    <button class="secondary" onclick="SubGraphManager.resetSubgraphCanvas('${this.fileId}')" title="Auto Fit View" style="font-size:0.7rem; padding:2px 7px; font-weight:600; background:var(--bg-surface); border:1px solid var(--border-subtle); backdrop-filter:blur(6px);">⛶ Fit</button>
                </div>
                <canvas id="${this.winId}-canvas"></canvas>
                <div class="subgraph-canvas-bar">
                    <div class="subgraph-canvas-left">
                        <span id="${this.winId}-stat-symbols">0 symbols</span>
                    </div>
                </div>
            </div>

            <div class="subgraph-panel" id="${this.winId}-panel-usages">
                <div class="usage-analysis-box" id="${this.winId}-usages-content">
                    <div style="color:var(--text-muted); text-align:center; padding:20px;">Analyzing incoming & outgoing references...</div>
                </div>
            </div>

            <div class="subgraph-panel" id="${this.winId}-panel-code">
                <div class="subgraph-editor-bar">
                    <div style="display:flex; align-items:center; gap:8px; margin-left:auto;">
                        <label class="subgraph-toggle-label" title="When enabled, saving writes directly to the project file on disk instead of in-memory override store">
                            <input type="checkbox" class="subgraph-toggle-disk-input" id="${this.winId}-toggle-disk" ${appState.directDiskWrite ? "checked" : ""} onchange="App.setDirectDiskEdit(this.checked)">
                            <span>💾 Direct Disk</span>
                        </label>
                        <button class="secondary" style="font-size:0.68rem; padding:2px 6px;" onclick="SubGraphManager.revertFile('${this.fileId}')">Revert</button>
                        <button class="success" style="font-size:0.68rem; padding:2px 8px;" onclick="SubGraphManager.saveFile('${this.fileId}')">Apply Edit</button>
                    </div>
                </div>
                <div class="editor-wrapper" id="${this.winId}-editor-wrapper">
                    <div class="line-numbers" id="${this.winId}-line-numbers"></div>
                    <div id="${this.winId}-symbol-highlight" class="symbol-highlight-overlay" style="display:none;"></div>
                    <div id="${this.winId}-error-highlight" class="error-highlight-overlay" style="display:none;"></div>
                    <textarea class="subgraph-textarea" id="${this.winId}-textarea" spellcheck="false"></textarea>
                </div>
            </div>
        `;

        container.appendChild(win);
        this.setupInteractions(win);
    }

    setupInteractions(win) {
        const header = document.getElementById(`${this.winId}-header`);
        const moveBtn = document.getElementById(`${this.winId}-move-btn`);
        let isDragging = false;
        let startX, startY, origLeft, origTop;

        const onDragStart = e => {
            if (!this.moveMode) return;
            if (e.target.closest("button") && e.target !== moveBtn) return;
            if (e.target.closest("select") || e.target.closest("input")) return;
            isDragging = true;
            const clientX = (e.touches && e.touches.length > 0) ? e.touches[0].clientX : (e.clientX ?? 0);
            const clientY = (e.touches && e.touches.length > 0) ? e.touches[0].clientY : (e.clientY ?? 0);
            startX = clientX;
            startY = clientY;
            origLeft = win.offsetLeft;
            origTop = win.offsetTop;
            win.style.zIndex = ++SubGraphManager.topZ;
            document.body.style.userSelect = "none";
        };

        const onDragMove = e => {
            if (!isDragging) return;
            const clientX = (e.touches && e.touches.length > 0) ? e.touches[0].clientX : (e.clientX ?? 0);
            const clientY = (e.touches && e.touches.length > 0) ? e.touches[0].clientY : (e.clientY ?? 0);
            const dx = clientX - startX;
            const dy = clientY - startY;
            win.style.left = `${Math.max(0, origLeft + dx)}px`;
            win.style.top = `${Math.max(0, origTop + dy)}px`;
        };

        const onDragEnd = () => {
            if (isDragging) {
                isDragging = false;
                document.body.style.userSelect = "";
            }
        };

        header.addEventListener("mousedown", onDragStart);
        header.addEventListener("touchstart", onDragStart, { passive: true });
        window.addEventListener("mousemove", onDragMove);
        window.addEventListener("touchmove", onDragMove, { passive: true });
        window.addEventListener("mouseup", onDragEnd);
        window.addEventListener("touchend", onDragEnd);

        win.addEventListener("mousedown", () => {
            win.style.zIndex = ++SubGraphManager.topZ;
        });
    }

    async loadData() {
        try {
            this.data = await CodeUIAPI.getSubGraph(this.fileId, this.targetSymbolId);
            const fileRes = await CodeUIAPI.getFile(this.fileId);
            this.fileContent = fileRes.content || "";
            if (fileRes.path && fileRes.path !== this.fileId && !fileRes.is_external) {
                const oldFileId = this.fileId;
                this.fileId = fileRes.path;
                appState.activeSubgraphs.set(this.fileId, this);
                appState.activeSubgraphs.set(oldFileId, this);
            }
            if (fileRes.resolved_symbol) this.targetSymbolId = this.targetSymbolId || fileRes.resolved_symbol;
            if (fileRes.target_line) this.targetLine = this.targetLine || fileRes.target_line;
            const isReallyExternal = Boolean(fileRes.is_external && this.data?.is_external);
            if (isReallyExternal) {
                this.isExternal = true;
                const pathEl = document.getElementById(`${this.winId}-header-path`);
                if (pathEl) {
                    pathEl.innerHTML = `<span class="badge shared" style="margin-right:6px; font-size:0.65rem;">🌐 External</span>${this.fileId}`;
                }
                const saveBtn = document.querySelector(`#${this.winId} button[onclick*="saveFile"]`);
                if (saveBtn) {
                    saveBtn.outerHTML = `<span class="badge shared" style="font-size:0.68rem; padding:2px 8px; font-weight:600;">ReadOnly</span>`;
                }
            }
            this.renderSymbolsGraph();
            this.renderUsages();
            this.renderEditor();
            if (this.initialTab === "code" || (this.targetLine && !this.targetSymbolId)) {
                SubGraphManager.switchTab(this.fileId, "code");
                if (this.targetSymbolId) {
                    this.scrollToSymbol(this.targetSymbolId);
                } else if (this.targetLine) {
                    this.highlightError(this.targetLine, this.targetMessage);
                }
            } else {
                SubGraphManager.switchTab(this.fileId, "graph");
                if (this.targetSymbolId && this.canvasInstance) {
                    const symName = this.targetSymbolId.split("::").pop();
                    const symNode = (this.canvasInstance.nodes || []).find(n =>
                        n.id === this.targetSymbolId || n.rawSymbol?.id === this.targetSymbolId || n.label === symName || n.id.endsWith("::" + symName)
                    );
                    if (symNode) {
                        this.canvasInstance.selectedNodeId = symNode.id;
                        this.canvasInstance.isolateNeighborhood(symNode.id);
                        if (this.updateSymbolBar) {
                            this.updateSymbolBar(symNode);
                        }
                    }
                }
            }
        } catch (e) {
            App.showToast(`Error loading ${this.fileId}: ${e.message}`, "error");
        }
    }

    renderSymbolsGraph() {
        const canvasId = `${this.winId}-canvas`;
        const canvasEl = document.getElementById(canvasId);
        if (!canvasEl) return;
        if (this.canvasInstance && this.canvasInstance.canvas !== canvasEl) {
            this.canvasInstance.destroy();
            this.canvasInstance = null;
        }
        if (!this.canvasInstance) {
            this.canvasInstance = new GraphCanvas(canvasId, false);
        }

        let localNodes = (this.data?.symbols || [])
            .filter(s => s && s.kind !== "file")
            .map(s => ({
                id: s.id,
                label: s.name,
                kind: s.kind,
                layer: this.data?.classification?.layer || "frontend",
                feature: this.data?.classification?.feature || "subgraph",
                radius: s.kind === "class" ? 14 : (s.kind === "function" ? 12 : 10),
                rawSymbol: s,
                isExternal: false,
                fileId: this.fileId
            }));

        if (localNodes.length === 0) {
            const fileName = this.fileId.split("/").pop();
            localNodes.push({
                id: this.fileId,
                label: fileName,
                kind: "file",
                layer: this.data?.classification?.layer || "shared",
                feature: this.data?.classification?.feature || "file",
                radius: 14,
                rawSymbol: { id: this.fileId, name: fileName, kind: "file" },
                isExternal: false,
                fileId: this.fileId
            });
        }

        const localSymIds = new Set(localNodes.map(n => n.id));

        let displayNodes = [...localNodes];
        let displayLinks = [];

        if (this.showCrossUsage) {
            const rawExt = Array.isArray(this.data?.related_symbols) ? this.data.related_symbols : Object.values(this.data?.related_symbols || {});
            const seenExtIds = new Set(localSymIds);
            const externalNodes = [];
            for (const s of rawExt) {
                if (!s || !s.id || seenExtIds.has(s.id)) continue;
                const fileForExt = s.file_id || s.location?.file_id || (s.id.includes("::") ? s.id.split("::")[0] : null);
                if (!fileForExt || fileForExt.startsWith("module::")) continue;
                if (fileForExt === this.fileId && s.kind !== "file") continue;
                seenExtIds.add(s.id);
                externalNodes.push({
                    id: s.id,
                    label: s.name || s.id.split("::").pop(),
                    kind: s.kind || "symbol",
                    layer: s.layer || "shared",
                    feature: s.feature || "external",
                    radius: s.kind === "class" ? 13 : (s.kind === "function" ? 11 : 9),
                    rawSymbol: s,
                    isExternal: true,
                    fileId: fileForExt
                });
            }
            displayNodes = [...localNodes, ...externalNodes];
            const allNodeIds = new Set(displayNodes.map(n => n.id));
            const hasLocalFileNode = localNodes.some(n => n.id === this.fileId);
            displayLinks = (this.data?.edges || []).filter(e => {
                const srcMatch = allNodeIds.has(e.source_id) || (hasLocalFileNode && e.source_id === this.fileId);
                const tgtMatch = allNodeIds.has(e.target_id) || (hasLocalFileNode && e.target_id === this.fileId);
                return srcMatch && tgtMatch && e.source_id !== e.target_id;
            }).map(e => ({
                source: allNodeIds.has(e.source_id) ? e.source_id : this.fileId,
                target: allNodeIds.has(e.target_id) ? e.target_id : this.fileId,
                kind: e.kind,
                weight: e.weight
            }));
        } else {
            displayLinks = (this.data?.edges || []).filter(e => localSymIds.has(e.source_id) && localSymIds.has(e.target_id)).map(e => ({
                source: e.source_id,
                target: e.target_id,
                kind: e.kind,
                weight: e.weight
            }));
        }

        this.canvasInstance.setData(displayNodes, displayLinks);
        setTimeout(() => {
            if (this.canvasInstance) this.canvasInstance.fitToScreen();
        }, 50);

        const updateSymbolBar = (node) => {
            const statEl = document.getElementById(`${this.winId}-stat-symbols`);
            if (!statEl) return;
            if (node) {
                const sym = node.rawSymbol || {};
                const safeName = (node.label || "").replace(/'/g, "\\'");
                const safeId = (node.id || "").replace(/'/g, "\\'");
                if (node.isExternal) {
                    const safeFile = (node.fileId || "").replace(/'/g, "\\'");
                    const incomingEdgesToLocal = (this.data?.edges || []).filter(e => e.source_id === node.id && localSymIds.has(e.target_id));
                    const outgoingEdgesFromLocal = (this.data?.edges || []).filter(e => e.target_id === node.id && localSymIds.has(e.source_id));
                    let relInfo = "";
                    if (incomingEdgesToLocal.length > 0) {
                        relInfo += `<span class="badge warning" style="font-size:0.65rem; background:rgba(234,179,8,0.2); color:var(--warning);" title="Calls ${incomingEdgesToLocal.length} symbol(s) in this file">⚡ Calls this file (${incomingEdgesToLocal.length})</span> `;
                    }
                    if (outgoingEdgesFromLocal.length > 0) {
                        relInfo += `<span class="badge shared" style="font-size:0.65rem;" title="Called by ${outgoingEdgesFromLocal.length} symbol(s) in this file">➡️ Called by this file (${outgoingEdgesFromLocal.length})</span> `;
                    }
                    statEl.innerHTML = `
                        <span class="badge shared" style="background:var(--accent); color:var(--bg-base); font-weight:700;">🌐 External</span>
                        <span style="font-weight:700; color:var(--text-main);">${node.label}</span>
                        <span style="font-size:0.68rem; color:var(--text-dim);" title="${node.fileId}">(${node.fileId ? node.fileId.split('/').pop() : 'other file'})</span>
                        ${relInfo}
                        <button class="secondary" style="padding:2px 8px; font-size:0.68rem; margin-left:6px; font-weight:600;" onclick="SubGraphManager.openWindow('${safeFile}', '${safeId}', null, '', 'graph')">📂 Open ${node.fileId ? node.fileId.split('/').pop() : 'File'}</button>
                        <button class="success" style="padding:2px 8px; font-size:0.68rem; margin-left:6px; font-weight:600;" onclick="SubGraphManager.openWindow('${safeFile}', '${safeId}', null, '', 'code')">✏️ Edit Symbol</button>
                    `;
                } else {
                    const affectedCallers = (this.data?.edges || []).filter(e => e.target_id === node.id && !localSymIds.has(e.source_id));
                    const outgoingCalls = (this.data?.edges || []).filter(e => e.source_id === node.id && !localSymIds.has(e.target_id));
                    let impactBadge = "";
                    if (affectedCallers.length > 0) {
                        impactBadge = `<span class="badge warning" style="margin-left:6px; font-size:0.68rem; background:rgba(234,179,8,0.2); color:var(--warning); border:1px solid rgba(234,179,8,0.4);" title="Modifying this symbol may affect ${affectedCallers.length} external caller node(s)">⚠️ ${affectedCallers.length} external caller(s) affected</span>`;
                    }
                    if (outgoingCalls.length > 0) {
                        impactBadge += ` <span class="badge shared" style="margin-left:4px; font-size:0.68rem;" title="Calls ${outgoingCalls.length} external dependencies">➡️ ${outgoingCalls.length} ext calls</span>`;
                    }
                    statEl.innerHTML = `
                        <span style="font-weight:700; color:var(--text-main);">${node.label}</span>
                        <span class="badge ${node.kind || 'other'}">${node.kind || 'symbol'}</span>
                        <button class="success" style="padding:2px 8px; font-size:0.68rem; margin-left:6px; font-weight:600;" onclick="SubGraphManager.editSymbol('${this.fileId}', '${safeId}')">✏️ Edit Symbol</button>
                        ${impactBadge}
                    `;
                }
            } else {
                const extCount = (this.data?.related_symbols || []).length;
                if (this.showCrossUsage && extCount > 0) {
                    statEl.innerHTML = `<span>${localNodes.length} local symbols, <span style="color:var(--purple, var(--accent)); font-weight:600;">+${extCount} cross-file impact nodes</span> (${displayLinks.length} total edges)</span>`;
                } else {
                    const availableCross = (this.data?.related_symbols || []).length;
                    const crossHint = availableCross > 0 ? ` <span style="color:var(--text-dim); font-size:0.65rem;">(${availableCross} cross-file nodes available)</span>` : "";
                    statEl.innerHTML = `<span>${localNodes.length} symbols, ${displayLinks.length} internal links${crossHint}</span>`;
                }
            }
        };

        this.updateSymbolBar = updateSymbolBar;

        let initialFocusNode = null;
        if (this.targetSymbolId) {
            const symName = this.targetSymbolId.split("::").pop();
            initialFocusNode = displayNodes.find(n =>
                n.id === this.targetSymbolId ||
                n.rawSymbol?.id === this.targetSymbolId ||
                n.label === symName ||
                n.id.endsWith("::" + symName)
            );
        }
        if (initialFocusNode) {
            this.canvasInstance.selectedNodeId = initialFocusNode.id;
            this.canvasInstance.isolateNeighborhood(initialFocusNode.id);
            updateSymbolBar(initialFocusNode);
        } else {
            updateSymbolBar(null);
        }

        this.canvasInstance.onNodeSelected = (node) => {
            this.targetSymbolId = node.id;
            this.canvasInstance.selectedNodeId = node.id;
            this.canvasInstance.isolateNeighborhood(node.id);
            updateSymbolBar(node);
            this.renderUsages();

            if (!node.isExternal) {
                this.scrollToSymbol(node.id);
            }
        };

        this.canvasInstance.onNodeDoubleClick = (node) => {
            if (node.isExternal) {
                SubGraphManager.openWindow(node.fileId, node.id, null, "", "graph");
            } else {
                this.targetSymbolId = node.id;
                SubGraphManager.editSymbol(this.fileId, node.id);
            }
        };

        this.canvasInstance.onEmptyCanvasClick = () => {
            this.targetSymbolId = null;
            this.canvasInstance.selectedNodeId = null;
            this.canvasInstance.clearNeighborhoodIsolation();
            updateSymbolBar(null);
            this.renderUsages();
        };
    }

    renderUsages() {
        const container = document.getElementById(`${this.winId}-usages-content`);
        if (!container) return;

        const allEdges = this.data?.edges || [];
        const selectedSymId = this.targetSymbolId;
        const selectedSymName = selectedSymId ? selectedSymId.replace("module::", "").split("::").pop() : "";

        const matchesTarget = (edgeEndpoint, targetId) => {
            if (!targetId || !edgeEndpoint) return false;
            if (edgeEndpoint === targetId) return true;
            const cleanEdge = edgeEndpoint.replace(/^module::/, "");
            const cleanTarget = targetId.replace(/^module::/, "");
            if (cleanEdge === cleanTarget) return true;
            if (cleanTarget.includes("::") && cleanEdge.includes("::")) {
                const [targetFile, targetScope] = cleanTarget.split("::");
                const [edgeFile, edgeScope] = cleanEdge.split("::");
                const fileMatches = targetFile === edgeFile || targetFile.endsWith("/" + edgeFile) || edgeFile.endsWith("/" + targetFile);
                return fileMatches && targetScope === edgeScope;
            }
            return false;
        };

        let extIncoming = [];
        let extOutgoing = [];

        if (selectedSymId) {
            extIncoming = allEdges.filter(e => matchesTarget(e.target_id, selectedSymId) && !matchesTarget(e.source_id, selectedSymId));
            extOutgoing = allEdges.filter(e => matchesTarget(e.source_id, selectedSymId) && !matchesTarget(e.target_id, selectedSymId));
        } else {
            extIncoming = allEdges.filter(e => e.source_id.split("::")[0] !== this.fileId);
            extOutgoing = allEdges.filter(e => e.target_id.split("::")[0] !== this.fileId);
        }

        let html = "";

        if (selectedSymId) {
            html += `
                <div class="usage-active-filter" style="display:flex; justify-content:space-between; align-items:center; background:var(--bg-elevated); padding:6px 10px; border-radius:6px; margin-bottom:8px; border:1px solid var(--accent); font-size:0.72rem;">
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span class="badge shared" style="font-size:0.65rem;">Symbol Filter</span>
                        <span style="font-weight:700; color:var(--text-main); font-size:0.75rem;">${selectedSymName}</span>
                    </div>
                    <button class="secondary" style="padding:2px 8px; font-size:0.68rem;" onclick="SubGraphManager.clearSymbolFilter('${this.fileId}')">View All File Usages</button>
                </div>
            `;
        }

        html += `<div class="usage-card">
            <div class="usage-card-title">
                <span>${selectedSymId ? `Incoming References to ${selectedSymName}` : "Incoming References (Called By)"}</span>
                <span class="badge shared">${extIncoming.length}</span>
            </div>`;
        if (extIncoming.length === 0) {
            html += `<div style="font-size:0.72rem; color:var(--text-dim); padding:4px;">${selectedSymId ? `No external callers found for '${selectedSymName}'.` : "No external files call this module."}</div>`;
        } else {
            extIncoming.forEach(e => {
                const srcFile = e.source_id.split("::")[0];
                const srcName = e.source_id.split("::")[1] || srcFile;
                html += `
                    <div class="usage-item" onclick="SubGraphManager.openWindow('${srcFile}', '${e.source_id}')">
                        <div>
                            <div style="font-weight:600; color:var(--text-main);">${srcName}</div>
                            <div style="font-size:0.65rem; color:var(--text-dim);">${srcFile}</div>
                        </div>
                        <span class="badge frontend">${e.kind}</span>
                    </div>
                `;
            });
        }
        html += `</div>`;

        html += `<div class="usage-card" style="margin-top:8px;">
            <div class="usage-card-title">
                <span>${selectedSymId ? `Outgoing Calls from ${selectedSymName}` : "Outgoing Calls (Depends On)"}</span>
                <span class="badge backend">${extOutgoing.length}</span>
            </div>`;
        if (extOutgoing.length === 0) {
            html += `<div style="font-size:0.72rem; color:var(--text-dim); padding:4px;">${selectedSymId ? `No outgoing calls found for '${selectedSymName}'.` : "No external calls from this module."}</div>`;
        } else {
            extOutgoing.forEach(e => {
                const tgtRaw = e.target_id.replace("module::", "");
                const tgtFile = tgtRaw.split("::")[0];
                const tgtName = tgtRaw.split("::")[1] || tgtRaw;
                html += `
                    <div class="usage-item" onclick="SubGraphManager.openWindow('${tgtFile}', '${e.target_id}')">
                        <div>
                            <div style="font-weight:600; color:var(--text-main);">${tgtName}</div>
                            <div style="font-size:0.65rem; color:var(--text-dim);">${tgtFile}</div>
                        </div>
                        <span class="badge shared">${e.kind}</span>
                    </div>
                `;
            });
        }
        html += `</div>`;

        container.innerHTML = html;
    }

    renderEditor() {
        const textarea = document.getElementById(`${this.winId}-textarea`);
        const lineNums = document.getElementById(`${this.winId}-line-numbers`);
        if (!textarea || !lineNums) return;

        textarea.value = this.fileContent;
        this.updateLineNumbers();

        textarea.addEventListener("input", () => {
            this.updateLineNumbers();
            this.updateHighlights();
        });

        textarea.addEventListener("scroll", () => {
            lineNums.scrollTop = textarea.scrollTop;
            this.updateHighlights();
        });

        if (this.targetSymbolId) {
            this.scrollToSymbol(this.targetSymbolId);
        }
    }

    updateLineNumbers() {
        const textarea = document.getElementById(`${this.winId}-textarea`);
        const lineNums = document.getElementById(`${this.winId}-line-numbers`);
        if (!textarea || !lineNums) return;
        const count = textarea.value.split("\n").length;
        lineNums.innerHTML = Array.from({ length: count }, (_, i) => i + 1).join("<br>");
    }

    getLineHeight() {
        const textarea = document.getElementById(`${this.winId}-textarea`);
        if (textarea) {
            const computed = window.getComputedStyle(textarea);
            const lh = parseFloat(computed.lineHeight);
            if (lh && !isNaN(lh) && lh > 0) return lh;
        }
        return 20;
    }

    scrollToSymbol(symbolId) {
        const textarea = document.getElementById(`${this.winId}-textarea`);
        const lineNums = document.getElementById(`${this.winId}-line-numbers`);
        if (!textarea) return;

        const cleanSymId = (symbolId || "").replace(/^module::/, "").trim();
        const symName = cleanSymId.split("::").pop();
        const shortName = symName && symName.includes(".") ? symName.split(".").pop() : (symName || "");

        let sym = null;
        if (this.canvasInstance?.nodes) {
            const foundNode = this.canvasInstance.nodes.find(n =>
                n.id === symbolId || n.id === cleanSymId ||
                n.rawSymbol?.id === symbolId || n.rawSymbol?.id === cleanSymId ||
                n.label === symName || n.label === shortName
            );
            if (foundNode && foundNode.rawSymbol && foundNode.rawSymbol.location) {
                sym = foundNode.rawSymbol;
            }
        }

        if (!sym && this.data?.symbols) {
            sym = this.data.symbols.find(s =>
                s.id === symbolId || s.id === cleanSymId ||
                s.name === symName || s.name === shortName ||
                s.qualified_name === symbolId || s.qualified_name === cleanSymId ||
                (symName && s.id.endsWith("::" + symName)) || (shortName && s.id.endsWith("::" + shortName))
            );
        }

        if (!sym && window.appState?.rawGraph?.symbols) {
            sym = window.appState.rawGraph.symbols.find(s =>
                (s.location?.file_id === this.fileId || s.id.startsWith(this.fileId + "::")) &&
                (s.id === symbolId || s.name === symName || s.name === shortName || (symName && s.id.endsWith("::" + symName)))
            );
        }

        let startLine = sym?.location?.start_line;
        let endLine = sym?.location?.end_line || startLine;

        if ((!startLine || startLine <= 0) && textarea.value && shortName) {
            const lines = textarea.value.split("\n");
            const defRegex = new RegExp(`(^|\\s)(class|def|function|const|let|var|type|interface)\\s+${shortName}\\b`);
            for (let i = 0; i < lines.length; i++) {
                if (defRegex.test(lines[i])) {
                    startLine = i + 1;
                    endLine = startLine + 10;
                    break;
                }
            }
            if (!startLine) {
                const wordRegex = new RegExp(`\\b${shortName}\\b`);
                for (let i = 0; i < lines.length; i++) {
                    if (wordRegex.test(lines[i])) {
                        startLine = i + 1;
                        endLine = startLine + 5;
                        break;
                    }
                }
            }
        }

        if (startLine && startLine > 0) {
            this.targetLine = startLine;
            this.targetEndLine = endLine || startLine;
            this.targetSymbolId = symbolId;

            const applyScrollAndHighlight = () => {
                const lineHeight = this.getLineHeight();
                const targetY = (startLine - 1) * lineHeight;

                textarea.scrollTop = Math.max(0, targetY - 40);
                if (lineNums) lineNums.scrollTop = textarea.scrollTop;

                const highlight = document.getElementById(`${this.winId}-symbol-highlight`);
                if (highlight) {
                    highlight.style.display = "block";
                    const numLines = Math.max(1, (endLine || startLine) - startLine + 1);
                    highlight.style.top = `${targetY - textarea.scrollTop + 8}px`;
                    highlight.style.height = `${numLines * lineHeight}px`;
                    highlight.title = `${sym?.signature || shortName} (Lines ${startLine}-${endLine || startLine})`;
                    highlight.innerHTML = `<span class="symbol-highlight-badge">⚡ ${sym?.name || shortName} (L${startLine}-${endLine || startLine})</span>`;
                }

                const lines = textarea.value.split("\n");
                let charStart = 0;
                for (let i = 0; i < startLine - 1 && i < lines.length; i++) {
                    charStart += lines[i].length + 1;
                }
                let charEnd = charStart;
                for (let i = startLine - 1; i < (endLine || startLine) && i < lines.length; i++) {
                    charEnd += lines[i].length + 1;
                }

                try {
                    textarea.setSelectionRange(charStart, charStart);
                } catch (_) {}

                textarea.scrollTop = Math.max(0, targetY - 40);
                if (lineNums) lineNums.scrollTop = textarea.scrollTop;
                if (highlight) {
                    highlight.style.top = `${targetY - textarea.scrollTop + 8}px`;
                }
            };

            applyScrollAndHighlight();
            requestAnimationFrame(() => applyScrollAndHighlight());
            setTimeout(() => applyScrollAndHighlight(), 50);
        }
    }

    highlightError(lineNumber, message = "") {
        const textarea = document.getElementById(`${this.winId}-textarea`);
        const lineNums = document.getElementById(`${this.winId}-line-numbers`);
        if (!textarea) return;
        this.targetErrorLine = lineNumber;

        const applyErrorScroll = () => {
            const lineHeight = this.getLineHeight();
            const targetY = (lineNumber - 1) * lineHeight;
            textarea.scrollTop = Math.max(0, targetY - 40);
            if (lineNums) lineNums.scrollTop = textarea.scrollTop;

            const errHighlight = document.getElementById(`${this.winId}-error-highlight`);
            if (errHighlight) {
                errHighlight.style.display = "block";
                errHighlight.style.top = `${targetY - textarea.scrollTop + 8}px`;
                errHighlight.style.height = `${lineHeight}px`;
                errHighlight.title = message;
                if (message) {
                    errHighlight.innerHTML = `<span class="error-badge" style="position:absolute; right:8px; top:1px; font-size:0.68rem; background:rgba(239,68,68,0.25); border:1px solid #ef4444; color:#f87171; padding:0 6px; border-radius:3px; pointer-events:none; white-space:nowrap; z-index:5;">🚨 L${lineNumber}: ${message}</span>`;
                } else {
                    errHighlight.innerHTML = "";
                }
            }

            const lines = textarea.value.split("\n");
            let charStart = 0;
            for (let i = 0; i < lineNumber - 1 && i < lines.length; i++) {
                charStart += lines[i].length + 1;
            }

            try {
                textarea.setSelectionRange(charStart, charStart);
            } catch (_) {}

            textarea.scrollTop = Math.max(0, targetY - 40);
            if (lineNums) lineNums.scrollTop = textarea.scrollTop;
            if (errHighlight) {
                errHighlight.style.top = `${targetY - textarea.scrollTop + 8}px`;
            }
        };

        applyErrorScroll();
        requestAnimationFrame(() => applyErrorScroll());
        setTimeout(() => applyErrorScroll(), 50);
    }

    updateHighlights() {
        const textarea = document.getElementById(`${this.winId}-textarea`);
        const highlight = document.getElementById(`${this.winId}-symbol-highlight`);
        const errHighlight = document.getElementById(`${this.winId}-error-highlight`);
        if (!textarea) return;
        const lineHeight = this.getLineHeight();

        if (highlight && highlight.style.display !== "none" && (this.targetLine || this.targetSymbolId)) {
            let startLine = this.targetLine;
            let endLine = this.targetEndLine || startLine;
            if (!startLine && this.targetSymbolId && this.data) {
                const symName = this.targetSymbolId.split("::").pop();
                const sym = (this.data.symbols || []).find(s =>
                    s.id === this.targetSymbolId || s.name === this.targetSymbolId || s.qualified_name === this.targetSymbolId ||
                    (symName && s.id.endsWith("::" + symName)) || s.name === symName
                );
                if (sym?.location?.start_line) {
                    startLine = sym.location.start_line;
                    endLine = sym.location.end_line || startLine;
                }
            }
            if (startLine && startLine > 0) {
                const targetY = (startLine - 1) * lineHeight;
                highlight.style.top = `${targetY - textarea.scrollTop + 8}px`;
                highlight.style.height = `${Math.max(1, (endLine || startLine) - startLine + 1) * lineHeight}px`;
            }
        }

        if (errHighlight && errHighlight.style.display !== "none" && this.targetErrorLine) {
            const targetY = (this.targetErrorLine - 1) * lineHeight;
            errHighlight.style.top = `${targetY - textarea.scrollTop + 8}px`;
        }
    }
}

class SubGraphManager {
    static topZ = 300;

    static getWindow(fileId) {
        if (!fileId) return null;
        const norm = fileId.replace(/\\/g, "/").trim();
        let win = appState.activeSubgraphs.get(norm) || appState.activeSubgraphs.get(fileId);
        if (win) return win;
        for (const [k, v] of appState.activeSubgraphs.entries()) {
            if (v.fileId === fileId || v.fileId === norm ||
                k.endsWith(norm) || norm.endsWith(k) ||
                k.endsWith(fileId) || fileId.endsWith(k) ||
                (v.fileId && (v.fileId.endsWith("/" + norm) || norm.endsWith("/" + v.fileId)))) {
                return v;
            }
        }
        return null;
    }

    static updateBackgroundInteractivity() {
        let hasActiveWindow = false;
        appState.activeSubgraphs.forEach(win => {
            if (!win || !win.winId) return;
            const dom = document.getElementById(win.winId);
            if (dom && dom.style.display !== "none" && !dom.classList.contains("minimized")) {
                hasActiveWindow = true;
            }
        });

        const mainCanvasEl = document.getElementById("graph-canvas");
        if (mainCanvasEl) {
            if (hasActiveWindow) {
                mainCanvasEl.classList.add("background-inert");
            } else {
                mainCanvasEl.classList.remove("background-inert");
            }
        }
        if (window.mainCanvas) {
            window.mainCanvas.isInteractive = !hasActiveWindow;
        }
    }

    static clearSymbolFilter(fileId) {
        const win = this.getWindow(fileId);
        if (!win) return;
        win.targetSymbolId = null;
        if (win.canvasInstance) {
            win.canvasInstance.selectedNodeId = null;
            win.canvasInstance.clearNeighborhoodIsolation();
        }
        if (win.updateSymbolBar) {
            win.updateSymbolBar(null);
        }
        win.renderUsages();
    }

    static toggleMoveMode(fileId) {
        const win = this.getWindow(fileId);
        if (!win) return;
        win.moveMode = !win.moveMode;
        const btn = document.getElementById(`${win.winId}-move-btn`);
        const header = document.getElementById(`${win.winId}-header`);
        if (btn) {
            btn.classList.toggle("active", win.moveMode);
            btn.classList.toggle("primary", win.moveMode);
        }
        if (header) {
            header.style.cursor = win.moveMode ? "move" : "default";
        }
    }

    static tileWindows() {
        const activeWins = [];
        const seenDomIds = new Set();

        appState.activeSubgraphs.forEach((win) => {
            if (win && win.winId && !seenDomIds.has(win.winId)) {
                seenDomIds.add(win.winId);
                const dom = document.getElementById(win.winId);
                if (dom && dom.style.display !== "none" && !dom.classList.contains("minimized") && !dom.classList.contains("maximized")) {
                    activeWins.push(win);
                }
            }
        });

        const count = activeWins.length;
        if (count === 0) return;

        const container = document.getElementById("canvas-container") || document.body;
        const containerW = container.clientWidth || window.innerWidth || 1000;
        const containerH = container.clientHeight || window.innerHeight || 700;

        const margin = 20;
        const gap = 16;
        const availW = Math.max(320, containerW - (margin * 2));
        const availH = Math.max(240, containerH - (margin * 2));

        let cols = 1;
        let rows = 1;

        if (count === 1) {
            cols = 1; rows = 1;
        } else if (count === 2) {
            if (availW >= 550) {
                cols = 2; rows = 1;
            } else {
                cols = 1; rows = 2;
            }
        } else if (count <= 4) {
            cols = 2; rows = 2;
        } else if (count <= 6) {
            cols = 3; rows = 2;
        } else {
            cols = Math.ceil(Math.sqrt(count));
            rows = Math.ceil(count / cols);
        }

        const winWidth = (count === 1)
            ? Math.min(640, availW)
            : Math.max(300, Math.floor((availW - (gap * (cols - 1))) / cols));

        const winHeight = (count === 1)
            ? Math.min(500, availH)
            : Math.max(240, Math.floor((availH - (gap * (rows - 1))) / rows));

        activeWins.forEach((win, index) => {
            const r = Math.floor(index / cols);
            const c = index % cols;
            const left = margin + c * (winWidth + gap);
            const top = margin + r * (winHeight + gap);

            const dom = document.getElementById(win.winId);
            if (dom) {
                dom.style.left = `${left}px`;
                dom.style.top = `${top}px`;
                dom.style.width = `${winWidth}px`;
                dom.style.height = `${winHeight}px`;
                if (win.canvasInstance) {
                    setTimeout(() => {
                        if (win.canvasInstance) {
                            win.canvasInstance.setupCanvas();
                            win.canvasInstance.fitToScreen();
                        }
                    }, 50);
                }
            }
        });
    }

    static openWindow(fileId, symbolId = null, line = null, message = "", initialTab = "graph") {
        if (!fileId) return;
        let clean = (fileId || "").replace(/^module::/, "").replace(/^\.\//, "").trim();
        let symId = symbolId;
        if (clean.includes("::")) {
            const parts = clean.split("::");
            clean = parts[0];
            if (!symId) symId = fileId;
        }

        const rawGraph = appState.rawGraph || {};
        const symList = rawGraph.symbols || [];
        const filesList = rawGraph.files || [];

        const symName = symId ? symId.split("::").pop().split(".").pop() : clean.split("::").pop().split(".").pop();
        const matched = symList.find(s =>
            s.id === clean || s.name === clean || s.qualified_name === clean ||
            (symId && (s.id === symId || s.name === symId || s.qualified_name === symId || s.name === symName || s.id.endsWith("::" + symName)))
        );
        if (matched && matched.location && matched.location.file_id) {
            clean = matched.location.file_id;
            if (!symId) symId = matched.id;
            if (!line && matched.location.start_line) line = matched.location.start_line;
        } else {
            let matchedFile = filesList.find(f =>
                f === clean || f.endsWith("/" + clean) || f.replace(/\.[^/.]+$/, "") === clean || f.endsWith("/" + clean + ".py") || f.endsWith("/" + clean + ".ts") || f.endsWith("/" + clean + ".js")
            );
            if (matchedFile) {
                clean = matchedFile;
            }
        }

        const normFileId = clean;
        const winDomId = `subgraph-win-${normFileId.replace(/[^a-zA-Z0-9]/g, "_")}`;

        let win = appState.activeSubgraphs.get(normFileId);
        if (!win) {
            for (const [key, existingWin] of appState.activeSubgraphs.entries()) {
                if (existingWin.fileId === normFileId || existingWin.winId === winDomId) {
                    win = existingWin;
                    break;
                }
            }
        }

        const dom = document.getElementById(winDomId);
        if (win || dom) {
            if (dom) {
                dom.classList.remove("minimized");
                dom.style.display = "flex";
                dom.style.zIndex = ++this.topZ;
            }
            if (win) {
                if (symId) {
                    win.targetSymbolId = symId;
                }
                if (line) {
                    win.targetLine = line;
                    win.targetMessage = message;
                }
                if (initialTab === "code" || (line && !symId)) {
                    this.switchTab(normFileId, "code");
                    if (symId) {
                        win.scrollToSymbol(symId);
                    } else if (line) {
                        win.highlightError(line, message);
                    }
                } else {
                    this.switchTab(normFileId, "graph");
                    if (symId && win.canvasInstance) {
                        const symName = symId.split("::").pop();
                        const symNode = (win.canvasInstance.nodes || []).find(n =>
                            n.id === symId || n.rawSymbol?.id === symId || n.label === symName || n.id.endsWith("::" + symName)
                        );
                        if (symNode) {
                            win.canvasInstance.selectedNodeId = symNode.id;
                            win.canvasInstance.isolateNeighborhood(symNode.id);
                            if (win.updateSymbolBar) {
                                win.updateSymbolBar(symNode);
                            }
                        }
                    }
                }
            }
            this.tileWindows();
            this.updateTaskbar();
            return;
        }

        const newWin = new SubGraphWindow(normFileId, symId, line, message, appState.nextWindowOffset, initialTab);
        appState.nextWindowOffset = (appState.nextWindowOffset + 35) % 250 + 20;
        appState.activeSubgraphs.set(normFileId, newWin);
        this.tileWindows();
        this.updateTaskbar();
        this.updateBackgroundInteractivity();
    }

    static closeWindow(fileId) {
        if (!fileId) return;
        const normFileId = fileId.replace(/^module::/, "").replace(/^\.\//, "").trim();
        let winToDelete = null;
        const keysToDelete = [];

        appState.activeSubgraphs.forEach((win, key) => {
            if (win.fileId === normFileId || win.fileId === fileId || key === normFileId || key === fileId || key.endsWith(normFileId)) {
                winToDelete = win;
                keysToDelete.push(key);
            }
        });

        if (winToDelete) {
            if (winToDelete.canvasInstance) {
                winToDelete.canvasInstance.destroy();
                winToDelete.canvasInstance = null;
            }
            const dom = document.getElementById(winToDelete.winId);
            if (dom) dom.remove();
            keysToDelete.forEach(k => appState.activeSubgraphs.delete(k));
        } else {
            const winDomId = `subgraph-win-${normFileId.replace(/[^a-zA-Z0-9]/g, "_")}`;
            const dom = document.getElementById(winDomId);
            if (dom) dom.remove();
        }

        this.tileWindows();
        this.updateTaskbar();
        this.updateBackgroundInteractivity();
    }

    static minimizeWindow(fileId) {
        if (!fileId) return;
        const normFileId = fileId.replace(/^module::/, "").replace(/^\.\//, "").trim();
        const win = appState.activeSubgraphs.get(normFileId) || appState.activeSubgraphs.get(fileId);
        if (win) {
            const dom = document.getElementById(win.winId);
            if (dom) dom.classList.add("minimized");
            this.tileWindows();
            this.updateTaskbar();
            this.updateBackgroundInteractivity();
        }
    }

    static maximizeWindow(fileId) {
        if (!fileId) return;
        const normFileId = fileId.replace(/^module::/, "").replace(/^\.\//, "").trim();
        const win = appState.activeSubgraphs.get(normFileId) || appState.activeSubgraphs.get(fileId);
        if (win) {
            const dom = document.getElementById(win.winId);
            if (dom) {
                dom.classList.toggle("maximized");
                if (win.canvasInstance) {
                    win.canvasInstance.setupCanvas();
                    win.canvasInstance.fitToScreen();
                }
            }
        }
    }

    static editSymbol(fileId, symbolId) {
        const win = this.getWindow(fileId);
        if (!win) return;
        win.targetSymbolId = symbolId;
        this.switchTab(fileId, "code");
        win.scrollToSymbol(symbolId);
    }

    static switchTab(fileId, tabName) {
        const win = this.getWindow(fileId);
        if (!win) return;
        const dom = document.getElementById(win.winId);
        if (!dom) return;

        dom.querySelectorAll(".subtab-btn").forEach(b => b.classList.remove("active"));
        dom.querySelectorAll(".subgraph-panel").forEach(p => p.classList.remove("active"));

        const tabBtn = dom.querySelector(`button[onclick*="'${tabName}'"]`);
        const panel = document.getElementById(`${win.winId}-panel-${tabName}`);
        if (tabBtn) tabBtn.classList.add("active");
        if (panel) panel.classList.add("active");

        if (tabName === "graph" && win.canvasInstance) {
            win.canvasInstance.setupCanvas();
            win.canvasInstance.fitToScreen();
            if (win.targetSymbolId) {
                const symName = win.targetSymbolId.split("::").pop();
                const symNode = (win.canvasInstance.nodes || []).find(n =>
                    n.id === win.targetSymbolId || n.rawSymbol?.id === win.targetSymbolId || n.label === symName || (symName && n.id.endsWith("::" + symName))
                );
                if (symNode) {
                    win.canvasInstance.selectedNodeId = symNode.id;
                    win.canvasInstance.isolateNeighborhood(symNode.id);
                    if (win.updateSymbolBar) {
                        win.updateSymbolBar(symNode);
                    }
                }
            }
        } else if (tabName === "code") {
            if (win.targetSymbolId) {
                win.scrollToSymbol(win.targetSymbolId);
            } else if (win.targetLine) {
                win.highlightError(win.targetLine, win.targetMessage);
            }
        }
    }

    static resetSubgraphCanvas(fileId) {
        const win = this.getWindow(fileId);
        if (win && win.canvasInstance) {
            win.canvasInstance.fitToScreen();
        }
    }

    static toggleCrossUsage(fileId, isEnabled) {
        let win = this.getWindow(fileId);
        if (!win) return;
        if (isEnabled === undefined) {
            win.showCrossUsage = !win.showCrossUsage;
        } else {
            win.showCrossUsage = !!isEnabled;
        }
        const btn = document.getElementById(`${win.winId}-btn-cross`);
        if (btn) {
            btn.classList.toggle("active", win.showCrossUsage);
            btn.classList.toggle("primary", win.showCrossUsage);
        }
        win.renderSymbolsGraph();
        if (win.canvasInstance) {
            setTimeout(() => {
                if (win.canvasInstance) {
                    win.canvasInstance.fitToScreen();
                }
            }, 60);
        }
    }

    static async saveFile(fileId) {
        let win = this.getWindow(fileId);
        if (!win) {
            App.showToast(`Error: Window for ${fileId} not found`, "error");
            return;
        }
        const textarea = document.getElementById(`${win.winId}-textarea`);
        if (!textarea) {
            App.showToast(`Error: Editor for ${fileId} not found`, "error");
            return;
        }

        const diskCheckbox = document.getElementById(`${win.winId}-toggle-disk`);
        const isDirect = !!(appState.directDiskWrite || (diskCheckbox && diskCheckbox.checked));
        const saveBtn = document.querySelector(`#${win.winId} button[onclick*="saveFile"]`);
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = "Saving...";
        }

        try {
            const res = await CodeUIAPI.applyEdit(win.fileId, textarea.value, "replace_file", isDirect);
            if (isDirect) {
                const displayPath = res.saved_path ? res.saved_path.split("/").slice(-2).join("/") : win.fileId;
                App.showToast(`Saved directly to disk: ${displayPath}`, "success");
            } else {
                App.showToast(`Saved non-destructive override for ${win.fileId}`, "success");
            }
            win.fileContent = textarea.value;
            App.loadData(false);
        } catch (e) {
            App.showToast(`Failed to save edit: ${e.message}`, "error");
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = "Apply Edit";
            }
        }
    }

    static async revertFile(fileId) {
        let win = this.getWindow(fileId);
        try {
            const target = win ? win.fileId : fileId;
            await CodeUIAPI.revertEdit(target);
            App.showToast(`Reverted overrides for ${target}`, "info");
            if (win) await win.loadData();
            App.loadData(false);
        } catch (e) {
            App.showToast(`Failed to revert: ${e.message}`, "error");
        }
    }

    static updateTaskbar() {
        const taskbar = document.getElementById("subgraph-taskbar");
        if (!taskbar) return;
        taskbar.innerHTML = "";

        appState.activeSubgraphs.forEach((win, fileId) => {
            const dom = document.getElementById(win.winId);
            const isMin = dom && dom.classList.contains("minimized");
            const filename = fileId.split("/").pop();

            const pill = document.createElement("div");
            pill.className = `taskbar-pill ${isMin ? "minimized" : ""}`;
            pill.innerHTML = `<span>📄</span> ${filename}`;
            pill.onclick = () => {
                if (dom) {
                    dom.classList.remove("minimized");
                    dom.style.zIndex = ++this.topZ;
                    this.tileWindows();
                    this.updateTaskbar();
                    this.updateBackgroundInteractivity();
                }
            };
            taskbar.appendChild(pill);
        });
    }
}

window.SubGraphManager = SubGraphManager;
window.addEventListener("resize", () => SubGraphManager.tileWindows());
