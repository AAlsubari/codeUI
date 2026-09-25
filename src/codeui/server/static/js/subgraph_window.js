/**
 * Multi-SubGraph Floating Windows Manager.
 * Supports multiple draggable, resizable, independent visualizer windows with code editor,
 * line numbers, error highlights, and bidirectional usage explorer.
 */
class SubGraphWindow {
    constructor(fileId, targetSymbolId = null, targetLine = null, targetMessage = "", initialOffset = 30) {
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
        this.winId = `subgraph-win-${this.fileId.replace(/[^a-zA-Z0-9]/g, "_")}`;
        this.data = null;
        this.fileContent = "";
        this.canvasInstance = null;
        this.offset = initialOffset;
        this.showCrossUsage = false;
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
                <div class="subgraph-window-title">
                    <span>📄</span>
                    <span title="${this.fileId}">${filename}</span>
                </div>
                <div class="subgraph-nav">
                    <button class="subtab-btn active" onclick="SubGraphManager.switchTab('${this.fileId}', 'graph')">Symbols Graph</button>
                    <button class="subtab-btn" onclick="SubGraphManager.switchTab('${this.fileId}', 'usages')">Cross Usages</button>
                    <button class="subtab-btn" onclick="SubGraphManager.switchTab('${this.fileId}', 'code')">Code Editor</button>
                </div>
                <div class="subgraph-window-actions">
                    <button class="btn-move-window secondary" id="${this.winId}-move-btn" title="Drag to Reposition Window" style="cursor:grab; padding:2px 8px; font-weight:700;">✥ Move</button>
                    <button class="secondary" onclick="SubGraphManager.minimizeWindow('${this.fileId}')">_</button>
                    <button class="secondary" onclick="SubGraphManager.maximizeWindow('${this.fileId}')">⛶</button>
                    <button class="danger" onclick="SubGraphManager.closeWindow('${this.fileId}')">✕</button>
                </div>
            </div>

            <!-- Panel 1: SubGraph Visualizer Canvas -->
            <div class="subgraph-panel active" id="${this.winId}-panel-graph">
                <canvas id="${this.winId}-canvas"></canvas>
                <div class="subgraph-canvas-bar">
                    <div class="subgraph-canvas-left">
                        <span id="${this.winId}-stat-symbols">0 symbols</span>
                    </div>
                    <div class="subgraph-canvas-right">
                        <label class="subgraph-toggle-label" id="${this.winId}-toggle-label" title="Toggle cross-file related symbols and usage dependencies to evaluate blast radius and impact">
                            <input type="checkbox" id="${this.winId}-toggle-cross" onchange="SubGraphManager.toggleCrossUsage('${this.fileId}', this.checked)">
                            <span>🌐 Related & Cross Usages</span>
                        </label>
                        <button class="secondary" style="padding:2px 8px; font-size:0.68rem;" onclick="SubGraphManager.resetSubgraphCanvas('${this.fileId}')">Fit View</button>
                    </div>
                </div>
            </div>

            <!-- Panel 2: Usages Explorer -->
            <div class="subgraph-panel" id="${this.winId}-panel-usages">
                <div class="usage-analysis-box" id="${this.winId}-usages-content">
                    <div style="color:var(--text-muted); text-align:center; padding:20px;">Analyzing incoming & outgoing references...</div>
                </div>
            </div>

            <!-- Panel 3: Code Editor -->
            <div class="subgraph-panel" id="${this.winId}-panel-code">
                <div class="subgraph-editor-bar">
                    <span style="font-size:0.7rem; color:var(--accent);" id="${this.winId}-editor-path">${this.fileId}</span>
                    <div style="display:flex; align-items:center; gap:8px;">
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

            <!-- Resizer Handle Bottom-Right -->
            <div class="subgraph-resize-handle" id="${this.winId}-resize-handle" title="Drag to Resize Window"></div>
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
            if (e.target.closest("button") && e.target !== moveBtn) return;
            if (e.target.closest("select") || e.target.closest("input")) return;
            isDragging = true;
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            startX = clientX;
            startY = clientY;
            origLeft = win.offsetLeft;
            origTop = win.offsetTop;
            win.style.zIndex = ++SubGraphManager.topZ;
            document.body.style.userSelect = "none";
        };

        const onDragMove = e => {
            if (!isDragging) return;
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
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

        // Window Resizer Logic
        const resizer = document.getElementById(`${this.winId}-resize-handle`);
        let isResizing = false;
        let initW, initH, startRX, startRY;

        const onResizeStart = e => {
            e.stopPropagation();
            isResizing = true;
            resizer.classList.add("active");
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            startRX = clientX;
            startRY = clientY;
            initW = win.offsetWidth;
            initH = win.offsetHeight;
            win.style.zIndex = ++SubGraphManager.topZ;
            document.body.style.userSelect = "none";
        };

        const onResizeMove = e => {
            if (!isResizing) return;
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            const newW = Math.max(300, initW + (clientX - startRX));
            const newH = Math.max(200, initH + (clientY - startRY));
            win.style.width = `${newW}px`;
            win.style.height = `${newH}px`;
            if (this.canvasInstance) {
                this.canvasInstance.setupCanvas();
            }
        };

        const onResizeEnd = () => {
            if (isResizing) {
                isResizing = false;
                resizer.classList.remove("active");
                document.body.style.userSelect = "";
            }
        };

        resizer.addEventListener("mousedown", onResizeStart);
        resizer.addEventListener("touchstart", onResizeStart, { passive: true });
        window.addEventListener("mousemove", onResizeMove);
        window.addEventListener("touchmove", onResizeMove, { passive: true });
        window.addEventListener("mouseup", onResizeEnd);
        window.addEventListener("touchend", onResizeEnd);

        win.addEventListener("mousedown", () => {
            win.style.zIndex = ++SubGraphManager.topZ;
        });
    }

    async loadData() {
        try {
            this.data = await CodeUIAPI.getSubGraph(this.fileId, this.targetSymbolId);
            const fileRes = await CodeUIAPI.getFile(this.fileId);
            this.fileContent = fileRes.content || "";
            this.renderSymbolsGraph();
            this.renderUsages();
            this.renderEditor();
            if (this.targetSymbolId || this.targetLine) {
                SubGraphManager.switchTab(this.fileId, "code");
            }
            if (this.targetLine) {
                this.highlightError(this.targetLine, this.targetMessage);
            }
        } catch (e) {
            App.showToast(`Error loading ${this.fileId}: ${e.message}`, "error");
        }
    }

    renderSymbolsGraph() {
        const canvasId = `${this.winId}-canvas`;
        const canvasEl = document.getElementById(canvasId);
        if (!canvasEl) return;
        if (this.canvasInstance) {
            this.canvasInstance.destroy();
            this.canvasInstance = null;
        }
        this.canvasInstance = new GraphCanvas(canvasId, false);

        const localNodes = (this.data?.symbols || []).map(s => ({
            id: s.id,
            label: s.name,
            kind: s.kind,
            layer: this.data?.classification?.layer || "frontend",
            feature: this.data?.classification?.feature || "subgraph",
            radius: s.kind === "class" ? 10 : (s.kind === "function" ? 8 : 6),
            rawSymbol: s,
            isExternal: false,
            fileId: this.fileId
        }));

        const localSymIds = new Set(localNodes.map(n => n.id));

        let displayNodes = [...localNodes];
        let displayLinks = [];

        if (this.showCrossUsage) {
            const externalNodes = (this.data?.related_symbols || []).map(s => ({
                id: s.id,
                label: s.name || s.id.split("::").pop(),
                kind: s.kind || "symbol",
                layer: s.layer || "shared",
                feature: s.feature || "external",
                radius: s.kind === "class" ? 9 : (s.kind === "function" ? 7 : 6),
                rawSymbol: s,
                isExternal: true,
                fileId: s.file_id || (s.id.includes("::") ? s.id.split("::")[0] : s.id)
            }));
            displayNodes = [...localNodes, ...externalNodes];
            const allNodeIds = new Set(displayNodes.map(n => n.id));
            displayLinks = (this.data?.edges || []).filter(e => allNodeIds.has(e.source_id) && allNodeIds.has(e.target_id)).map(e => ({
                source: e.source_id,
                target: e.target_id,
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
                        relInfo += `<span class="badge warning" style="font-size:0.65rem; background:rgba(234,179,8,0.2); color:#facc15;" title="Calls ${incomingEdgesToLocal.length} symbol(s) in this file">⚡ Calls this file (${incomingEdgesToLocal.length})</span> `;
                    }
                    if (outgoingEdgesFromLocal.length > 0) {
                        relInfo += `<span class="badge shared" style="font-size:0.65rem;" title="Called by ${outgoingEdgesFromLocal.length} symbol(s) in this file">➡️ Called by this file (${outgoingEdgesFromLocal.length})</span> `;
                    }
                    statEl.innerHTML = `
                        <span class="badge shared" style="background:#4338ca; color:#e0e7ff; font-weight:700;">🌐 External</span>
                        <span style="font-weight:700; color:var(--text-main);">${node.label}</span>
                        <span style="font-size:0.68rem; color:var(--text-dim);" title="${node.fileId}">(${node.fileId ? node.fileId.split('/').pop() : 'other file'})</span>
                        ${relInfo}
                        <button class="secondary" style="padding:2px 8px; font-size:0.68rem; margin-left:6px; font-weight:600;" onclick="SubGraphManager.openWindow('${safeFile}', '${safeId}')">📂 Open ${node.fileId ? node.fileId.split('/').pop() : 'File'}</button>
                    `;
                } else {
                    const affectedCallers = (this.data?.edges || []).filter(e => e.target_id === node.id && !localSymIds.has(e.source_id));
                    const outgoingCalls = (this.data?.edges || []).filter(e => e.source_id === node.id && !localSymIds.has(e.target_id));
                    let impactBadge = "";
                    if (affectedCallers.length > 0) {
                        impactBadge = `<span class="badge warning" style="margin-left:6px; font-size:0.68rem; background:rgba(234,179,8,0.2); color:#facc15; border:1px solid rgba(234,179,8,0.4);" title="Modifying this symbol may affect ${affectedCallers.length} external caller node(s) across other files">⚠️ ${affectedCallers.length} external caller(s) affected</span>`;
                    }
                    if (outgoingCalls.length > 0) {
                        impactBadge += ` <span class="badge shared" style="margin-left:4px; font-size:0.68rem;" title="Calls ${outgoingCalls.length} external dependency(ies)">➡️ ${outgoingCalls.length} ext calls</span>`;
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
                    statEl.innerHTML = `<span>${localNodes.length} local symbols, <span style="color:#a855f7; font-weight:600;">+${extCount} cross-file impact nodes</span> (${displayLinks.length} total edges)</span>`;
                } else {
                    const availableCross = (this.data?.related_symbols || []).length;
                    const crossHint = availableCross > 0 ? ` <span style="color:var(--text-dim); font-size:0.65rem;">(${availableCross} cross-file nodes available)</span>` : "";
                    statEl.innerHTML = `<span>${localNodes.length} symbols, ${displayLinks.length} internal links${crossHint}</span>`;
                }
            }
        };

        this.canvasInstance.onNodeSelected = (node) => {
            if (!node.isExternal) {
                this.targetSymbolId = node.id;
            }
            updateSymbolBar(node);
        };

        this.canvasInstance.onNodeDoubleClick = (node) => {
            if (node.isExternal) {
                SubGraphManager.openWindow(node.fileId, node.id);
            } else {
                this.targetSymbolId = node.id;
                SubGraphManager.editSymbol(this.fileId, node.id);
            }
        };

        this.canvasInstance.onEmptyCanvasClick = () => {
            this.targetSymbolId = null;
            updateSymbolBar(null);
        };

        updateSymbolBar(null);
    }

    renderUsages() {
        const container = document.getElementById(`${this.winId}-usages-content`);
        if (!container) return;

        const extIncoming = (this.data.edges || []).filter(e => e.source_id.split("::")[0] !== this.fileId);
        const extOutgoing = (this.data.edges || []).filter(e => e.target_id.split("::")[0] !== this.fileId);

        let html = "";

        // Incoming Dependencies
        html += `<div class="usage-card">
            <div class="usage-card-title">
                <span>Incoming References (Called By)</span>
                <span class="badge shared">${extIncoming.length}</span>
            </div>`;
        if (extIncoming.length === 0) {
            html += `<div style="font-size:0.72rem; color:var(--text-dim); padding:4px;">No external files call this module.</div>`;
        } else {
            extIncoming.forEach(e => {
                const srcFile = e.source_id.split("::")[0];
                const srcName = e.source_id.split("::")[1] || srcFile;
                html += `
                    <div class="usage-item" onclick="SubGraphManager.openWindow('${srcFile}')">
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

        // Outgoing Dependencies
        html += `<div class="usage-card" style="margin-top:8px;">
            <div class="usage-card-title">
                <span>Outgoing Calls (Depends On)</span>
                <span class="badge backend">${extOutgoing.length}</span>
            </div>`;
        if (extOutgoing.length === 0) {
            html += `<div style="font-size:0.72rem; color:var(--text-dim); padding:4px;">No external calls from this module.</div>`;
        } else {
            extOutgoing.forEach(e => {
                const tgtRaw = e.target_id.replace("module::", "");
                const tgtFile = tgtRaw.split("::")[0];
                const tgtName = tgtRaw.split("::")[1] || tgtRaw;
                html += `
                    <div class="usage-item" onclick="SubGraphManager.openWindow('${tgtFile}')">
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

    scrollToSymbol(symbolId) {
        const textarea = document.getElementById(`${this.winId}-textarea`);
        const lineNums = document.getElementById(`${this.winId}-line-numbers`);
        if (!textarea) return;

        const symName = (symbolId || "").split("::").pop();
        let sym = (this.data?.symbols || []).find(s =>
            s.id === symbolId || s.name === symbolId || s.qualified_name === symbolId ||
            s.id.endsWith("::" + symName) || s.name === symName
        );

        let startLine = sym?.location?.start_line;
        let endLine = sym?.location?.end_line || startLine;

        // Fallback: search source content if symbol location wasn't provided in metadata
        if ((!startLine || startLine <= 0) && textarea.value && symName) {
            const lines = textarea.value.split("\n");
            for (let i = 0; i < lines.length; i++) {
                const l = lines[i];
                if (l.includes(`def ${symName}`) || l.includes(`class ${symName}`) || l.includes(`function ${symName}`) || l.includes(`const ${symName}`) || l.includes(symName)) {
                    startLine = i + 1;
                    endLine = startLine + 10;
                    break;
                }
            }
        }

        if (startLine && startLine > 0) {
            const lineHeight = 20;
            const targetY = (startLine - 1) * lineHeight;

            textarea.scrollTop = Math.max(0, targetY - 40);
            if (lineNums) lineNums.scrollTop = textarea.scrollTop;

            const highlight = document.getElementById(`${this.winId}-symbol-highlight`);
            if (highlight) {
                highlight.style.display = "block";
                const numLines = Math.max(1, (endLine || startLine) - startLine + 1);
                highlight.style.top = `${targetY - textarea.scrollTop + 8}px`;
                highlight.style.height = `${numLines * lineHeight}px`;
                highlight.title = `${sym?.signature || symName} (Lines ${startLine}-${endLine || startLine})`;
                highlight.innerHTML = `<span class="symbol-highlight-badge">⚡ ${sym?.name || symName} (L${startLine}-${endLine || startLine})</span>`;
            }

            const lines = textarea.value.split("\n");
            let charStart = 0;
            for (let i = 0; i < startLine - 1 && i < lines.length; i++) {
                charStart += lines[i].length + 1;
            }
            try {
                textarea.focus();
                textarea.setSelectionRange(charStart, charStart);
            } catch (_) {}
        }
    }

    highlightError(lineNumber, message = "") {
        const textarea = document.getElementById(`${this.winId}-textarea`);
        const lineNums = document.getElementById(`${this.winId}-line-numbers`);
        if (!textarea) return;
        const lineHeight = 20;
        const targetY = (lineNumber - 1) * lineHeight;
        textarea.scrollTop = Math.max(0, targetY - 40);
        if (lineNums) lineNums.scrollTop = textarea.scrollTop;

        const errHighlight = document.getElementById(`${this.winId}-error-highlight`);
        if (errHighlight) {
            errHighlight.style.display = "block";
            errHighlight.style.top = `${targetY - textarea.scrollTop + 8}px`;
            errHighlight.style.height = `${lineHeight}px`;
            errHighlight.title = message;
        }

        const lines = textarea.value.split("\n");
        let charStart = 0;
        for (let i = 0; i < lineNumber - 1 && i < lines.length; i++) {
            charStart += lines[i].length + 1;
        }
        try {
            textarea.focus();
            textarea.setSelectionRange(charStart, charStart);
        } catch (_) {}
    }

    updateHighlights() {
        const textarea = document.getElementById(`${this.winId}-textarea`);
        const highlight = document.getElementById(`${this.winId}-symbol-highlight`);
        const errHighlight = document.getElementById(`${this.winId}-error-highlight`);
        const lineHeight = 20;

        if (highlight && highlight.style.display !== "none" && this.targetSymbolId && this.data) {
            const symName = this.targetSymbolId.split("::").pop();
            const sym = (this.data.symbols || []).find(s =>
                s.id === this.targetSymbolId || s.name === this.targetSymbolId || s.qualified_name === this.targetSymbolId ||
                s.id.endsWith("::" + symName) || s.name === symName
            );
            if (sym && sym.location) {
                const targetY = (sym.location.start_line - 1) * lineHeight;
                highlight.style.top = `${targetY - textarea.scrollTop + 8}px`;
            }
        }
        if (errHighlight && errHighlight.style.display !== "none" && this.targetLine) {
            const targetY = (this.targetLine - 1) * lineHeight;
            errHighlight.style.top = `${targetY - textarea.scrollTop + 8}px`;
        }
    }
}

/**
 * Manager coordinating multiple floating SubGraph visualizer windows.
 */
class SubGraphManager {
    static topZ = 30;

    static openWindow(fileId, symbolId = null, line = null, message = "") {
        if (!fileId) return;
        let clean = (fileId || "").replace(/^module::/, "").replace(/^\.\//, "").trim();
        let symId = symbolId;
        if (clean.includes("::")) {
            const parts = clean.split("::");
            clean = parts[0];
            if (!symId) symId = fileId;
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
                    this.switchTab(normFileId, "code");
                    win.scrollToSymbol(symId);
                } else if (line) {
                    win.targetLine = line;
                    win.targetMessage = message;
                    this.switchTab(normFileId, "code");
                    win.highlightError(line, message);
                }
            }
            this.updateTaskbar();
            return;
        }

        const newWin = new SubGraphWindow(normFileId, symId, line, message, appState.nextWindowOffset);
        appState.nextWindowOffset = (appState.nextWindowOffset + 35) % 250 + 20;
        appState.activeSubgraphs.set(normFileId, newWin);
        this.updateTaskbar();
    }

    static closeWindow(fileId) {
        if (!fileId) return;
        const normFileId = fileId.replace(/^module::/, "").replace(/^\.\//, "").trim();
        const win = appState.activeSubgraphs.get(normFileId) || appState.activeSubgraphs.get(fileId);
        if (win) {
            if (win.canvasInstance) {
                win.canvasInstance.destroy();
                win.canvasInstance = null;
            }
            const dom = document.getElementById(win.winId);
            if (dom) dom.remove();
            appState.activeSubgraphs.delete(normFileId);
            appState.activeSubgraphs.delete(fileId);
        } else {
            const winDomId = `subgraph-win-${normFileId.replace(/[^a-zA-Z0-9]/g, "_")}`;
            const dom = document.getElementById(winDomId);
            if (dom) dom.remove();
        }
        this.updateTaskbar();
    }

    static minimizeWindow(fileId) {
        if (!fileId) return;
        const normFileId = fileId.replace(/^module::/, "").replace(/^\.\//, "").trim();
        const win = appState.activeSubgraphs.get(normFileId) || appState.activeSubgraphs.get(fileId);
        if (win) {
            const dom = document.getElementById(win.winId);
            if (dom) dom.classList.add("minimized");
            this.updateTaskbar();
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
        const win = appState.activeSubgraphs.get(fileId);
        if (!win) return;
        win.targetSymbolId = symbolId;
        this.switchTab(fileId, "code");
        setTimeout(() => win.scrollToSymbol(symbolId), 40);
    }

    static switchTab(fileId, tabName) {
        const win = appState.activeSubgraphs.get(fileId);
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
        } else if (tabName === "code") {
            setTimeout(() => {
                if (win.targetSymbolId) {
                    win.scrollToSymbol(win.targetSymbolId);
                } else if (win.targetLine) {
                    win.highlightError(win.targetLine, win.targetMessage);
                }
            }, 40);
        }
    }

    static resetSubgraphCanvas(fileId) {
        const win = appState.activeSubgraphs.get(fileId);
        if (win && win.canvasInstance) {
            win.canvasInstance.fitToScreen();
        }
    }

    static toggleCrossUsage(fileId, isEnabled) {
        const win = appState.activeSubgraphs.get(fileId);
        if (!win) return;
        win.showCrossUsage = isEnabled;
        const toggleLabel = document.getElementById(`${win.winId}-toggle-label`);
        if (toggleLabel) {
            toggleLabel.classList.toggle("active", isEnabled);
        }
        win.renderSymbolsGraph();
    }

    static async saveFile(fileId) {
        let win = appState.activeSubgraphs.get(fileId);
        if (!win) {
            for (const [k, v] of appState.activeSubgraphs.entries()) {
                if (v.fileId === fileId || k.endsWith(fileId) || fileId.endsWith(k)) {
                    win = v;
                    break;
                }
            }
        }
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
        let win = appState.activeSubgraphs.get(fileId);
        if (!win) {
            for (const [k, v] of appState.activeSubgraphs.entries()) {
                if (v.fileId === fileId || k.endsWith(fileId) || fileId.endsWith(k)) {
                    win = v;
                    break;
                }
            }
        }
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
                    this.updateTaskbar();
                }
            };
            taskbar.appendChild(pill);
        });
    }
}

window.SubGraphManager = SubGraphManager;
