/**
 * Collapsible Explorer Sidebar & Tab Views Manager.
 */
class Sidebar {
    static activeTab = "files";

    static toggleSidebar() {
        const sidebar = document.getElementById("sidebar");
        const dockBtn = document.getElementById("btn-dock-sidebar");
        if (!sidebar) return;

        sidebar.classList.toggle("collapsed");
        const isCollapsed = sidebar.classList.contains("collapsed");
        if (dockBtn) dockBtn.style.display = isCollapsed ? "flex" : "none";

        setTimeout(() => {
            if (window.mainCanvas) {
                window.mainCanvas.setupCanvas();
            }
        }, 260);
    }

    static switchTab(tabName) {
        this.activeTab = tabName;
        document.querySelectorAll(".sidebar-tabs .tab-btn").forEach(b => {
            b.classList.toggle("active", b.getAttribute("onclick").includes(tabName));
        });
        this.renderCurrentTab();
    }

    static renderCurrentTab() {
        const content = document.getElementById("sidebar-tab-content");
        if (!content) return;

        if (this.activeTab === "files") this.renderFilesTab(content);
        else if (this.activeTab === "features") this.renderFeaturesTab(content);
        else if (this.activeTab === "defects") this.renderDefectsTab(content);
        else if (this.activeTab === "stats") this.renderStatsTab(content);
    }

    static renderFilesTab(container) {
        const query = (document.getElementById("search-box")?.value || "").toLowerCase();
        const filesInfo = appState.rawGraph.files_info || {};
        const files = (appState.rawGraph.files || []).filter(f => f.toLowerCase().includes(query));

        let html = `
            <div class="layer-filters">
                <span class="filter-chip ${appState.activeLayerFilter === 'all' ? 'active' : ''}" onclick="Sidebar.setLayerFilter('all')">All</span>
                <span class="filter-chip ${appState.activeLayerFilter === 'entry' ? 'active' : ''}" onclick="Sidebar.setLayerFilter('entry')">Entry</span>
                <span class="filter-chip ${appState.activeLayerFilter === 'frontend' ? 'active' : ''}" onclick="Sidebar.setLayerFilter('frontend')">Frontend</span>
                <span class="filter-chip ${appState.activeLayerFilter === 'backend' ? 'active' : ''}" onclick="Sidebar.setLayerFilter('backend')">Backend</span>
                <span class="filter-chip ${appState.activeLayerFilter === 'shared' ? 'active' : ''}" onclick="Sidebar.setLayerFilter('shared')">Shared</span>
                <span class="filter-chip ${appState.activeLayerFilter === 'test' ? 'active' : ''}" onclick="Sidebar.setLayerFilter('test')">Tests</span>
            </div>
            <div style="font-size:0.7rem; color:var(--text-muted); margin-bottom:6px;">Showing ${files.length} project files</div>
        `;

        files.forEach(f => {
            const info = filesInfo[f] || { layer: "other", feature: "root", symbols_count: 0 };
            if (appState.activeLayerFilter !== "all" && info.layer !== appState.activeLayerFilter) return;

            const isSelected = appState.selectedFileNodeId === f;
            const filename = f.split("/").pop();

            html += `
                <div class="item-card ${isSelected ? 'active' : ''}" id="card-${f.replace(/[^a-zA-Z0-9]/g, '_')}" onclick="Sidebar.onFileCardClick('${f}')">
                    <div class="item-header">
                        <span class="item-title">${filename}</span>
                        <span class="badge ${info.layer}">${info.layer}</span>
                    </div>
                    <div class="item-sub">${f}</div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
                        <span style="font-size:0.68rem; color:var(--accent);">${info.feature || 'root'}</span>
                        <span style="font-size:0.65rem; color:var(--text-dim);">${info.symbols_count || 0} symbols</span>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    static onFileCardClick(fileId) {
        appState.selectedFileNodeId = fileId;
        this.highlightSelectedCard(fileId);
        window.mainCanvas?.isolateNeighborhood(fileId);
        SubGraphManager.openWindow(fileId);
        const node = (window.mainCanvas?.nodes || []).find(n => n.id === fileId);
        if (node && window.mainCanvas) {
            window.mainCanvas.panTo(node.x, node.y);
        }
    }

    static clearSelection() {
        document.querySelectorAll(".item-card").forEach(c => c.classList.remove("active"));
    }

    static highlightSelectedCard(nodeId) {
        document.querySelectorAll(".item-card").forEach(c => c.classList.remove("active"));
        const card = document.getElementById(`card-${nodeId.replace(/[^a-zA-Z0-9]/g, '_')}`);
        if (card) {
            card.classList.add("active");
            card.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
    }

    static setLayerFilter(layer) {
        appState.activeLayerFilter = layer;
        this.renderCurrentTab();
        App.applyGraphFilter();
    }

    static renderFeaturesTab(container) {
        const filesInfo = appState.rawGraph.files_info || {};
        const featuresMap = new Map();

        Object.entries(filesInfo).forEach(([f, info]) => {
            const feat = info.feature || "root";
            if (!featuresMap.has(feat)) featuresMap.set(feat, []);
            featuresMap.get(feat).push(f);
        });

        let html = `<div style="font-size:0.7rem; color:var(--text-muted); margin-bottom:6px;">Architectural Feature Clusters</div>`;

        featuresMap.forEach((files, feat) => {
            const color = appState.getFeatureColor(feat);
            html += `
                <div class="item-card" style="border-left: 3px solid ${color};">
                    <div class="item-header">
                        <span class="item-title" style="color:${color};">${feat}</span>
                        <span class="badge" style="background:${color}22; color:${color};">${files.length} files</span>
                    </div>
                    <div style="font-size:0.7rem; color:var(--text-muted); margin-top:4px;">
                        ${files.slice(0, 3).map(f => f.split('/').pop()).join(', ')}${files.length > 3 ? '...' : ''}
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    static renderDefectsTab(container) {
        const defects = (appState.defectsData || []).filter(d => !appState.ignoredDefectIds.has(d.id) && !appState.ignoredRuleIds.has(d.rule_id));

        let html = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="font-size:0.75rem; font-weight:700; color:var(--danger);">Defect Findings (${defects.length})</span>
                ${(appState.ignoredDefectIds.size > 0 || appState.ignoredRuleIds.size > 0) ? `<button class="secondary" style="font-size:0.65rem; padding:2px 6px;" id="btn-restore-defects">Reset Ignored</button>` : ''}
            </div>
        `;

        if (defects.length === 0) {
            html += `<div style="color:var(--success); text-align:center; padding:20px; font-size:0.75rem;">✓ No active defects or code smell violations found!</div>`;
            container.innerHTML = html;
            return;
        }

        defects.forEach((d, idx) => {
            const loc = d.location || { file_id: "unknown", start_line: 1 };
            const isErr = d.severity === "error";
            const safeFile = this.escapeHtml(loc.file_id || "");
            const safeMsg = this.escapeHtml(d.message || "");
            const safeRule = this.escapeHtml(d.rule_id || "");
            const safeHint = d.fix_hint ? this.escapeHtml(d.fix_hint) : "";
            const safeId = this.escapeHtml(d.id || `defect-${idx}`);
            const safeSymId = this.escapeHtml(d.symbol_id || "");

            html += `
                <div class="item-card" style="border-left: 3px solid ${isErr ? 'var(--danger)' : 'var(--warning)'};">
                    <div class="item-header">
                        <span class="item-title" style="color:${isErr ? '#fca5a5' : '#fde68a'};">${safeRule}</span>
                        <span class="badge ${d.severity}">${d.severity}</span>
                    </div>
                    <div style="font-size:0.72rem; color:#cbd5e1; margin-top:4px;">${safeMsg}</div>
                    <div class="item-sub">${safeFile}:${loc.start_line}</div>
                    ${safeHint ? `<div style="font-size:0.68rem; color:var(--accent); margin-top:4px; font-style:italic;">Fix: ${safeHint}</div>` : ''}
                    <div class="defect-actions">
                        <button class="secondary btn-defect-view" data-file="${safeFile}" data-line="${loc.start_line}" data-sym="${safeSymId}" data-msg="${safeMsg}">View Code</button>
                        <button class="secondary btn-defect-ignore" data-id="${safeId}">Ignore Finding</button>
                        <button class="secondary btn-rule-ignore" data-rule="${safeRule}">Ignore Rule</button>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;

        container.querySelectorAll(".btn-defect-view").forEach(btn => {
            btn.addEventListener("click", () => {
                const file = btn.getAttribute("data-file");
                const line = parseInt(btn.getAttribute("data-line") || "1", 10);
                const sym = btn.getAttribute("data-sym") || "";
                const msg = btn.getAttribute("data-msg") || "";
                Sidebar.openDefectLocation(file, line, sym, msg);
            });
        });

        container.querySelectorAll(".btn-defect-ignore").forEach(btn => {
            btn.addEventListener("click", () => {
                Sidebar.ignoreDefect(btn.getAttribute("data-id"));
            });
        });

        container.querySelectorAll(".btn-rule-ignore").forEach(btn => {
            btn.addEventListener("click", () => {
                Sidebar.ignoreRule(btn.getAttribute("data-rule"));
            });
        });

        const restoreBtn = container.querySelector("#btn-restore-defects");
        if (restoreBtn) {
            restoreBtn.addEventListener("click", () => Sidebar.restoreAllIgnoredDefects());
        }
    }

    static escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    static openDefectLocation(fileId, line, symbolId, message) {
        SubGraphManager.openWindow(fileId, symbolId, line, message);
        SubGraphManager.switchTab(fileId, "code");
    }

    static ignoreDefect(defectId) {
        appState.ignoredDefectIds.add(defectId);
        this.renderCurrentTab();
        App.showToast("Finding ignored for this session", "info");
    }

    static ignoreRule(ruleId) {
        appState.ignoredRuleIds.add(ruleId);
        this.renderCurrentTab();
        App.showToast(`Rule '${ruleId}' ignored`, "info");
    }

    static restoreAllIgnoredDefects() {
        appState.ignoredDefectIds.clear();
        appState.ignoredRuleIds.clear();
        this.renderCurrentTab();
        App.showToast("All defect findings restored", "info");
    }

    static renderStatsTab(container) {
        const filesCount = (appState.rawGraph.files || []).length;
        const symsCount = (appState.rawGraph.symbols || []).length;
        const edgesCount = (appState.rawGraph.edges || []).length;
        const defectsCount = (appState.defectsData || []).length;

        container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-val">${filesCount}</div><div class="stat-lbl">Files</div></div>
                <div class="stat-card"><div class="stat-val">${symsCount}</div><div class="stat-lbl">Symbols</div></div>
                <div class="stat-card"><div class="stat-val">${edgesCount}</div><div class="stat-lbl">Dependencies</div></div>
                <div class="stat-card"><div class="stat-val" style="color:var(--danger);">${defectsCount}</div><div class="stat-lbl">Defects</div></div>
            </div>
            <div style="font-size:0.72rem; color:var(--text-muted); line-height:1.5; padding:6px;">
                <strong>Universal Code Intelligence</strong><br>
                Interactive dependency visualizer, defect detector, and non-destructive override environment.
            </div>
        `;
    }
}

window.Sidebar = Sidebar;
