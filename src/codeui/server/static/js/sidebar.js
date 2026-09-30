/**
 * Explorer Sidebar Controller for CodeUI.
 */
class Sidebar {
    static currentTab = "files";
    static collapsed = true;

    static init() {
        this.collapsed = true;
        const sidebar = document.getElementById("sidebar");
        const dockBtn = document.getElementById("btn-dock-sidebar");
        if (sidebar) sidebar.classList.add("collapsed");
        if (dockBtn) dockBtn.style.display = "flex";
        if (window.mainCanvas) {
            setTimeout(() => window.mainCanvas.handleResize(), 100);
        }
    }

    static switchTab(tabName) {
        this.currentTab = tabName;
        document.querySelectorAll(".sidebar-tabs .tab-btn").forEach(btn => {
            const active = btn.getAttribute("onclick")?.includes(`'${tabName}'`);
            btn.classList.toggle("active", !!active);
        });
        this.renderCurrentTab();
    }

    static toggleSidebar() {
        this.collapsed = !this.collapsed;
        const sidebar = document.getElementById("sidebar");
        const dockBtn = document.getElementById("btn-dock-sidebar");
        if (sidebar) sidebar.classList.toggle("collapsed", this.collapsed);
        if (dockBtn) dockBtn.style.display = this.collapsed ? "flex" : "none";
        if (window.mainCanvas) {
            setTimeout(() => window.mainCanvas.handleResize(), 200);
        }
    }

    static renderCurrentTab() {
        const container = document.getElementById("sidebar-tab-content");
        if (!container || !window.appState) return;

        const q = (appState.searchQuery || "").toLowerCase();
        const graph = appState.rawGraph || {};

        if (this.currentTab === "files") {
            const files = (graph.files || []).filter(f => !q || f.toLowerCase().includes(q));
            if (files.length === 0) {
                container.innerHTML = `<div class="empty-state" style="padding:16px; text-align:center; color:var(--text-dim); font-size:0.75rem;">No files found matching filter</div>`;
                return;
            }
            const info = graph.files_info || {};
            let html = `<div class="file-card-list">`;
            files.forEach(f => {
                const meta = info[f] || {};
                const layer = meta.layer || "other";
                const isSelected = appState.selectedFileNodeId === f;
                html += `
                    <div class="sidebar-item file-card ${isSelected ? 'selected' : ''}" data-id="${f}" onclick="Sidebar.onFileCardClick('${f}')">
                        <div class="file-title" style="display:flex; align-items:center; gap:6px; font-weight:600; font-size:0.8rem; color:var(--text-main);">
                            <span class="file-icon">📄</span>
                            <span class="file-name" title="${f}">${f.split('/').pop()}</span>
                        </div>
                        <div class="file-meta" style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
                            <span class="badge layer-${layer}" style="font-size:0.65rem; padding:1px 5px; border-radius:4px; text-transform:uppercase; background:var(--bg-surface); border:1px solid var(--border-subtle); color:var(--text-muted);">${layer}</span>
                            <span class="file-path" style="font-size:0.68rem; color:var(--text-dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:140px;" title="${f}">${f}</span>
                        </div>
                    </div>
                `;
            });
            html += `</div>`;
            container.innerHTML = html;
        } else if (this.currentTab === "features") {
            const info = graph.files_info || {};
            const featureMap = {};
            (graph.files || []).forEach(f => {
                if (q && !f.toLowerCase().includes(q)) return;
                const feat = info[f]?.feature || "root";
                if (!featureMap[feat]) featureMap[feat] = [];
                featureMap[feat].push(f);
            });

            const entries = Object.entries(featureMap);
            if (entries.length === 0) {
                container.innerHTML = `<div class="empty-state" style="padding:16px; text-align:center; color:var(--text-dim); font-size:0.75rem;">No features found</div>`;
                return;
            }

            let html = `<div class="feature-group-list">`;
            entries.forEach(([feat, fList]) => {
                const featColor = appState.getFeatureColor(feat);
                html += `
                    <div class="feature-group" style="margin-bottom:12px;">
                        <div class="feature-header" style="display:flex; align-items:center; justify-content:space-between; padding:6px 8px; background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:6px; margin-bottom:4px; font-size:0.75rem; font-weight:700;">
                            <div style="display:flex; align-items:center; gap:6px;">
                                <span class="legend-shape" style="background:${featColor}; display:inline-block; width:10px; height:10px; border-radius:50%;"></span>
                                <span class="feature-name" style="color:var(--text-main);">${feat}</span>
                            </div>
                            <span class="count-badge" style="background:var(--bg-base); padding:1px 6px; border-radius:10px; font-size:0.68rem; color:var(--text-muted);">${fList.length}</span>
                        </div>
                        <div class="feature-files">
                            ${fList.map(f => `
                                <div class="sidebar-item file-card" data-id="${f}" style="padding:4px 8px; margin:2px 0;" onclick="Sidebar.onFileCardClick('${f}')">
                                    <span class="file-name" style="font-size:0.75rem; color:var(--text-main);">${f.split('/').pop()}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            });
            html += `</div>`;
            container.innerHTML = html;
        } else if (this.currentTab === "defects") {
            const allFindings = appState.defectsData || [];
            const apiDriftCount = allFindings.filter(d => d.rule_id === "api_drift").length;
            const defectsCount = allFindings.length - apiDriftCount;

            if (!this.defectSubFilter) this.defectSubFilter = "all";

            const defects = allFindings.filter(d => {
                if (this.defectSubFilter === "api_drift" && d.rule_id !== "api_drift") return false;
                if (this.defectSubFilter === "defects" && d.rule_id === "api_drift") return false;
                return !q || d.rule_id.toLowerCase().includes(q) || (d.message || "").toLowerCase().includes(q);
            });

            let html = `
                <div class="defect-filter-bar" style="display:flex; gap:4px; margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid var(--border-subtle); flex-wrap:wrap; align-items:center;">
                    <button class="secondary ${this.defectSubFilter === 'all' ? 'active' : ''}" style="font-size:0.68rem; padding:2px 6px;" onclick="Sidebar.setDefectSubFilter('all')">All (${allFindings.length})</button>
                    <button class="secondary ${this.defectSubFilter === 'defects' ? 'active' : ''}" style="font-size:0.68rem; padding:2px 6px;" onclick="Sidebar.setDefectSubFilter('defects')">Defects (${defectsCount})</button>
                    <button class="secondary ${this.defectSubFilter === 'api_drift' ? 'active' : ''}" style="font-size:0.68rem; padding:2px 6px; color:var(--accent);" onclick="Sidebar.setDefectSubFilter('api_drift')">🌊 API Drift (${apiDriftCount})</button>
                    <button class="secondary" style="font-size:0.65rem; padding:2px 6px; color:var(--accent); border-color:var(--border-subtle); margin-left:auto;" onclick="App.setApiBaseline()" title="Capture public symbols baseline snapshot">📸 Set Baseline</button>
                </div>
            `;

            if (defects.length === 0) {
                html += `<div class="empty-state" style="padding:16px; text-align:center; color:var(--text-dim); font-size:0.75rem;">No findings or API drift issues detected under current filter</div>`;
                container.innerHTML = html;
                return;
            }

            html += `<div class="defects-card-list">`;
            defects.forEach(d => {
                const loc = d.location || {};
                const fId = loc.file_id || "unknown";
                const line = loc.start_line || 1;
                const isDrift = d.rule_id === "api_drift";
                const badgeColor = isDrift ? "var(--accent)" : "var(--danger)";
                const badgeLabel = isDrift ? "🌊 API Drift" : `⚠️ ${d.rule_id}`;
                const safeMsg = (d.message || "").replace(/'/g, "\\'");
                const symbolId = d.symbol_id || "";
                html += `
                    <div class="sidebar-item defect-card" style="padding:8px; border:1px solid ${isDrift ? 'var(--accent)' : 'var(--border-subtle)'}; border-radius:6px; margin-bottom:6px; background:var(--bg-surface); cursor:pointer;" onclick="Sidebar.openDefectLocation('${fId}', ${line}, '${symbolId}', '${safeMsg}')">
                        <div class="defect-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <span class="defect-rule" style="font-weight:700; font-size:0.75rem; color:${badgeColor};">${badgeLabel}</span>
                            <span class="defect-loc" style="font-size:0.68rem; color:var(--text-dim);">${fId.split('/').pop()}:${line}</span>
                        </div>
                        <div class="defect-msg" style="font-size:0.72rem; color:var(--text-muted); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">${d.message}</div>
                        ${d.fix_hint ? `<div style="font-size:0.65rem; color:var(--accent); margin-top:4px; font-style:italic;">💡 ${d.fix_hint}</div>` : ''}
                    </div>
                `;
            });
            html += `</div>`;
            container.innerHTML = html;
        } else if (this.currentTab === "stats") {
            const filesCount = (graph.files || []).length;
            const symbolsCount = (graph.symbols || []).length;
            const edgesCount = (graph.edges || []).length;
            const allFindings = appState.defectsData || [];
            const defectsCount = allFindings.filter(d => d.rule_id !== "api_drift").length;
            const apiDriftCount = allFindings.filter(d => d.rule_id === "api_drift").length;

            const layerCounts = {};
            const info = graph.files_info || {};
            (graph.files || []).forEach(f => {
                const l = info[f]?.layer || "other";
                layerCounts[l] = (layerCounts[l] || 0) + 1;
            });

            let html = `
                <div class="stats-panel" style="padding:8px;">
                    <div class="stats-grid" style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                        <div class="stat-card" style="background:var(--bg-surface); padding:8px; border-radius:6px; border:1px solid var(--border-subtle); text-align:center;">
                            <div class="stat-num" style="font-size:1.1rem; font-weight:800; color:var(--primary);">${filesCount}</div>
                            <div class="stat-label" style="font-size:0.68rem; color:var(--text-dim);">Files</div>
                        </div>
                        <div class="stat-card" style="background:var(--bg-surface); padding:8px; border-radius:6px; border:1px solid var(--border-subtle); text-align:center;">
                            <div class="stat-num" style="font-size:1.1rem; font-weight:800; color:var(--primary);">${symbolsCount}</div>
                            <div class="stat-label" style="font-size:0.68rem; color:var(--text-dim);">Symbols</div>
                        </div>
                        <div class="stat-card" style="background:var(--bg-surface); padding:8px; border-radius:6px; border:1px solid var(--border-subtle); text-align:center;">
                            <div class="stat-num" style="font-size:1.1rem; font-weight:800; color:var(--primary);">${edgesCount}</div>
                            <div class="stat-label" style="font-size:0.68rem; color:var(--text-dim);">Edges</div>
                        </div>
                        <div class="stat-card" style="background:var(--bg-surface); padding:8px; border-radius:6px; border:1px solid var(--border-subtle); text-align:center;">
                            <div class="stat-num" style="font-size:1.1rem; font-weight:800; color:var(--danger);">${defectsCount}</div>
                            <div class="stat-label" style="font-size:0.68rem; color:var(--text-dim);">Defects</div>
                        </div>
                        <div class="stat-card" style="background:var(--bg-surface); padding:8px; border-radius:6px; border:1px solid var(--border-subtle); grid-column: span 2; text-align:center;">
                            <div class="stat-num" style="font-size:1.1rem; font-weight:800; color:var(--accent);">${apiDriftCount}</div>
                            <div class="stat-label" style="font-size:0.68rem; color:var(--text-dim);">Public API Drift Warnings</div>
                        </div>
                    </div>
                    <div style="margin-top:16px; font-weight:700; font-size:0.8rem; color:var(--text-muted);">Layers Distribution</div>
                    <div class="layers-list" style="margin-top:8px;">
            `;
            Object.entries(layerCounts).forEach(([l, count]) => {
                const color = appState.LAYER_COLORS[l] || "var(--text-dim)";
                html += `
                    <div class="layer-stat-row" style="display:flex; justify-content:space-between; align-items:center; padding:4px 0; font-size:0.75rem;">
                        <span><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${color}; margin-right:6px;"></span>${l}</span>
                        <span style="color:var(--text-muted); font-weight:600;">${count} files</span>
                    </div>
                `;
            });
            html += `</div></div>`;
            container.innerHTML = html;
        }
    }

    static setDefectSubFilter(sub) {
        this.defectSubFilter = sub;
        this.renderCurrentTab();
    }

    static highlightSelectedCard(nodeId) {
        this.clearSelection();
        if (!nodeId) return;
        const cards = document.querySelectorAll(`.sidebar-item[data-id="${nodeId}"]`);
        cards.forEach(card => {
            card.classList.add("selected");
            card.scrollIntoView({ block: "nearest", behavior: "smooth" });
        });
    }

    static clearSelection() {
        document.querySelectorAll(".sidebar-item.selected").forEach(c => c.classList.remove("selected"));
    }

    static onFileCardClick(fileId) {
        appState.selectedFileNodeId = fileId;
        this.highlightSelectedCard(fileId);
        if (window.mainCanvas) {
            window.mainCanvas.selectAndCenterNode(fileId);
        }
    }

    static openDefectLocation(fileId, line = 1, symbol = null, message = "") {
        let targetSymbol = symbol && symbol.length > 0 ? symbol : null;
        if (!targetSymbol && appState.rawGraph?.symbols) {
            const fileSyms = appState.rawGraph.symbols.filter(s => {
                const sFile = s.location?.file_id;
                return sFile === fileId || sFile?.endsWith("/" + fileId) || fileId.endsWith("/" + sFile);
            });
            const match = fileSyms.find(s =>
                s.location &&
                s.location.start_line <= line &&
                (s.location.end_line || s.location.start_line) >= line
            );
            if (match) targetSymbol = match.id;
        }

        if (window.SubGraphManager) {
            SubGraphManager.openWindow(fileId, targetSymbol, line, message, "graph");
        }
    }
}

window.Sidebar = Sidebar;
