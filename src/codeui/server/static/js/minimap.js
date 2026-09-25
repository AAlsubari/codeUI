/**
 * Interactive Mini-Map Component for codeui Main Graph Visualization.
 * Provides live architectural overview, spatial orientation, and click/drag camera panning for large codebases.
 */
class MiniMap {
    constructor(mainCanvas) {
        this.mainCanvas = mainCanvas;
        this.container = document.getElementById("graph-minimap-container");
        this.dockBtn = document.getElementById("minimap-dock-btn");
        this.canvas = document.getElementById("minimap-canvas");
        this.countEl = document.getElementById("minimap-count");
        this.dockCountEl = document.getElementById("minimap-dock-count");
        this.tooltip = document.getElementById("minimap-tooltip");
        this.ctx = this.canvas ? this.canvas.getContext("2d") : null;
        this.cssWidth = 220;
        this.cssHeight = 140;
        this.isCollapsed = false;
        this.isDragging = false;
        this.lastMouse = { x: 0, y: 0 };
        this.mapping = {
            scale: 1,
            offsetX: 0,
            offsetY: 0,
            vfX: 0,
            vfY: 0,
            vfW: 0,
            vfH: 0,
            boundsMinX: 0,
            boundsMaxX: 0,
            boundsMinY: 0,
            boundsMaxY: 0
        };

        if (this.canvas) {
            this.setupEvents();
            this.resizeCanvas();
            this.restoreState();
        }
    }

    restoreState() {
        try {
            const saved = localStorage.getItem("codeui_minimap_collapsed");
            if (saved === "1" || (window.innerWidth <= 768 && saved === null)) {
                this.collapse();
            }
        } catch (_) {}
    }

    collapse() {
        this.isCollapsed = true;
        if (this.container) this.container.style.display = "none";
        if (this.dockBtn) this.dockBtn.style.display = "flex";
        try {
            localStorage.setItem("codeui_minimap_collapsed", "1");
        } catch (_) {}
    }

    expand() {
        this.isCollapsed = false;
        if (this.container) this.container.style.display = "flex";
        if (this.dockBtn) this.dockBtn.style.display = "none";
        try {
            localStorage.setItem("codeui_minimap_collapsed", "0");
        } catch (_) {}
        this.resizeCanvas();
        this.update();
    }

    resizeCanvas() {
        if (!this.canvas) return;
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = this.cssWidth * dpr;
        this.canvas.height = this.cssHeight * dpr;
        this.ctx.setTransform(1, 0, 0, 1, 0, 0);
        this.ctx.scale(dpr, dpr);
    }

    getMinimapPos(e) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }

    isInsideViewfinder(x, y) {
        const { vfX, vfY, vfW, vfH } = this.mapping;
        const hitPad = 4;
        return (
            x >= vfX - hitPad &&
            x <= vfX + vfW + hitPad &&
            y >= vfY - hitPad &&
            y <= vfY + vfH + hitPad
        );
    }

    setupEvents() {
        if (!this.canvas) return;

        const onDown = (clientX, clientY) => {
            const rect = this.canvas.getBoundingClientRect();
            const posX = clientX - rect.left;
            const posY = clientY - rect.top;

            if (this.isInsideViewfinder(posX, posY)) {
                this.isDragging = true;
                this.lastMouse = { x: clientX, y: clientY };
                this.canvas.style.cursor = "grabbing";
            } else {
                const worldX = (posX - this.mapping.offsetX) / this.mapping.scale;
                const worldY = (posY - this.mapping.offsetY) / this.mapping.scale;
                this.mainCanvas.panTo(worldX, worldY, false);
                this.isDragging = true;
                this.lastMouse = { x: clientX, y: clientY };
                this.canvas.style.cursor = "grabbing";
            }
        };

        const onMove = (clientX, clientY) => {
            if (this.isDragging) {
                const dx = (clientX - this.lastMouse.x) / this.mapping.scale;
                const dy = (clientY - this.lastMouse.y) / this.mapping.scale;
                this.mainCanvas.transform.x -= dx * this.mainCanvas.transform.k;
                this.mainCanvas.transform.y -= dy * this.mainCanvas.transform.k;
                this.lastMouse = { x: clientX, y: clientY };
                if (this.tooltip) this.tooltip.style.display = "none";
                return;
            }

            const rect = this.canvas.getBoundingClientRect();
            const posX = clientX - rect.left;
            const posY = clientY - rect.top;

            if (this.isInsideViewfinder(posX, posY)) {
                this.canvas.style.cursor = "grab";
            } else {
                this.canvas.style.cursor = "crosshair";
            }

            if (this.tooltip) {
                let hoveredNode = null;
                const nodes = this.mainCanvas.nodes || [];
                for (let i = nodes.length - 1; i >= 0; i--) {
                    const n = nodes[i];
                    const nx = n.x * this.mapping.scale + this.mapping.offsetX;
                    const ny = n.y * this.mapping.scale + this.mapping.offsetY;
                    const d2 = (nx - posX) * (nx - posX) + (ny - posY) * (ny - posY);
                    if (d2 <= 49) {
                        hoveredNode = n;
                        break;
                    }
                }
                if (hoveredNode) {
                    this.tooltip.textContent = hoveredNode.label || hoveredNode.id;
                    const tipX = Math.max(6, Math.min(posX + 8, this.cssWidth - 90));
                    const tipY = Math.max(4, posY - 26);
                    this.tooltip.style.left = `${tipX}px`;
                    this.tooltip.style.top = `${tipY}px`;
                    this.tooltip.style.display = "block";
                } else {
                    this.tooltip.style.display = "none";
                }
            }
        };

        const onUp = () => {
            this.isDragging = false;
            this.canvas.style.cursor = "crosshair";
        };

        this.canvas.addEventListener("mousedown", e => {
            e.preventDefault();
            onDown(e.clientX, e.clientY);
        });

        window.addEventListener("mousemove", e => {
            if (this.isDragging) {
                onMove(e.clientX, e.clientY);
            }
        });

        this.canvas.addEventListener("mousemove", e => {
            if (!this.isDragging) {
                onMove(e.clientX, e.clientY);
            }
        });

        window.addEventListener("mouseup", onUp);
        this.canvas.addEventListener("mouseleave", () => {
            if (!this.isDragging && this.tooltip) {
                this.tooltip.style.display = "none";
            }
        });

        this.canvas.addEventListener("wheel", e => {
            e.preventDefault();
            const factor = e.deltaY < 0 ? 1.15 : 0.85;
            this.mainCanvas.zoomBy(factor);
        }, { passive: false });

        this.canvas.addEventListener("touchstart", e => {
            if (e.touches.length === 1) {
                e.preventDefault();
                onDown(e.touches[0].clientX, e.touches[0].clientY);
            }
        }, { passive: false });

        this.canvas.addEventListener("touchmove", e => {
            if (e.touches.length === 1) {
                e.preventDefault();
                onMove(e.touches[0].clientX, e.touches[0].clientY);
            }
        }, { passive: false });

        this.canvas.addEventListener("touchend", onUp);
        this.canvas.addEventListener("touchcancel", onUp);
    }

    update() {
        if (!this.mainCanvas || !this.mainCanvas.nodes) return;
        const nodes = this.mainCanvas.nodes;
        const modeLabel = appState.graphMode === "files" ? "files" : "symbols";
        const countText = `${nodes.length} ${modeLabel}`;
        if (this.countEl && this.countEl.textContent !== countText) {
            this.countEl.textContent = countText;
        }
        if (this.dockCountEl && this.dockCountEl.textContent !== `(${countText})`) {
            this.dockCountEl.textContent = `(${countText})`;
        }
        if (this.isCollapsed || !this.ctx || !this.canvas) return;

        const mainContainer = document.getElementById("canvas-container");
        const mainW = mainContainer ? mainContainer.clientWidth || 800 : 800;
        const mainH = mainContainer ? mainContainer.clientHeight || 600 : 600;
        const k = this.mainCanvas.transform ? this.mainCanvas.transform.k || 1 : 1;
        const tx = this.mainCanvas.transform ? this.mainCanvas.transform.x || 0 : 0;
        const ty = this.mainCanvas.transform ? this.mainCanvas.transform.y || 0 : 0;

        const visMinX = -tx / k;
        const visMinY = -ty / k;
        const visMaxX = (mainW - tx) / k;
        const visMaxY = (mainH - ty) / k;

        let nMinX = Infinity, nMaxX = -Infinity, nMinY = Infinity, nMaxY = -Infinity;
        for (let i = 0; i < nodes.length; i++) {
            const n = nodes[i];
            if (isFinite(n.x) && isFinite(n.y)) {
                if (n.x < nMinX) nMinX = n.x;
                if (n.x > nMaxX) nMaxX = n.x;
                if (n.y < nMinY) nMinY = n.y;
                if (n.y > nMaxY) nMaxY = n.y;
            }
        }
        if (nMinX === Infinity || nodes.length === 0) {
            nMinX = -200; nMaxX = 200; nMinY = -150; nMaxY = 150;
        }

        const pad = 40;
        const boundsMinX = Math.min(nMinX - pad, isFinite(visMinX) ? visMinX : -200);
        const boundsMaxX = Math.max(nMaxX + pad, isFinite(visMaxX) ? visMaxX : 200);
        const boundsMinY = Math.min(nMinY - pad, isFinite(visMinY) ? visMinY : -150);
        const boundsMaxY = Math.max(nMaxY + pad, isFinite(visMaxY) ? visMaxY : 150);

        const spanX = Math.max(80, boundsMaxX - boundsMinX);
        const spanY = Math.max(60, boundsMaxY - boundsMinY);

        const scaleX = (this.cssWidth - 14) / spanX;
        const scaleY = (this.cssHeight - 14) / spanY;
        const scale = Math.max(0.001, Math.min(scaleX, scaleY));

        const midX = (boundsMinX + boundsMaxX) / 2;
        const midY = (boundsMinY + boundsMaxY) / 2;

        const offsetX = this.cssWidth / 2 - midX * scale;
        const offsetY = this.cssHeight / 2 - midY * scale;

        const vfX = isFinite(visMinX) ? visMinX * scale + offsetX : 0;
        const vfY = isFinite(visMinY) ? visMinY * scale + offsetY : 0;
        const vfW = isFinite(visMaxX) && isFinite(visMinX) ? (visMaxX - visMinX) * scale : this.cssWidth;
        const vfH = isFinite(visMaxY) && isFinite(visMinY) ? (visMaxY - visMinY) * scale : this.cssHeight;

        this.mapping = {
            scale, offsetX, offsetY,
            vfX, vfY, vfW, vfH,
            boundsMinX, boundsMaxX, boundsMinY, boundsMaxY
        };

        this.ctx.clearRect(0, 0, this.cssWidth, this.cssHeight);

        // Faint coordinate background dots
        this.ctx.fillStyle = "rgba(51, 65, 85, 0.35)";
        for (let gx = 10; gx < this.cssWidth; gx += 20) {
            for (let gy = 10; gy < this.cssHeight; gy += 20) {
                this.ctx.fillRect(gx, gy, 1, 1);
            }
        }

        // 1. Draw Links
        const links = this.mainCanvas.links || [];
        this.ctx.strokeStyle = "rgba(71, 85, 105, 0.35)";
        this.ctx.lineWidth = 0.8;
        this.ctx.beginPath();
        for (let i = 0; i < links.length; i++) {
            const l = links[i];
            const sx = l.source.x * scale + offsetX;
            const sy = l.source.y * scale + offsetY;
            const targetX = l.target.x * scale + offsetX;
            const targetY = l.target.y * scale + offsetY;
            this.ctx.moveTo(sx, sy);
            this.ctx.lineTo(targetX, targetY);
        }
        this.ctx.stroke();

        // 2. Draw Nodes
        const selNodeId = appState.selectedFileNodeId;
        const unusedNodeIds = appState.unusedHighlightMode ? appState.getUnusedNodeIds() : null;

        for (let i = 0; i < nodes.length; i++) {
            const n = nodes[i];
            const nx = n.x * scale + offsetX;
            const ny = n.y * scale + offsetY;
            const isSelected = selNodeId && n.id === selNodeId;

            let color = appState.colorMode === "feature"
                ? appState.getFeatureColor(n.feature)
                : (appState.LAYER_COLORS[n.layer] || "#0284c7");

            if (unusedNodeIds && unusedNodeIds.has(n.id) && !isSelected) {
                color = "#94a3b8";
            }

            const r = isSelected ? 4 : 2.5;
            this.ctx.beginPath();
            this.ctx.arc(nx, ny, r, 0, Math.PI * 2);
            this.ctx.fillStyle = color;
            this.ctx.fill();

            if (isSelected) {
                this.ctx.beginPath();
                this.ctx.arc(nx, ny, r + 2.5, 0, Math.PI * 2);
                this.ctx.strokeStyle = "#38bdf8";
                this.ctx.lineWidth = 1.5;
                this.ctx.stroke();
            }
        }

        // 3. Draw Viewfinder (Frustum Rectangle)
        this.ctx.fillStyle = "rgba(56, 189, 248, 0.12)";
        this.ctx.fillRect(vfX, vfY, vfW, vfH);
        this.ctx.strokeStyle = "#38bdf8";
        this.ctx.lineWidth = 1.5;
        this.ctx.strokeRect(vfX, vfY, vfW, vfH);

        // Corner accents for camera view
        const cornerLen = Math.min(6, Math.max(2, Math.min(vfW, vfH) / 3));
        if (cornerLen > 2) {
            this.ctx.strokeStyle = "#ffffff";
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            // Top-left
            this.ctx.moveTo(vfX, vfY + cornerLen);
            this.ctx.lineTo(vfX, vfY);
            this.ctx.lineTo(vfX + cornerLen, vfY);
            // Top-right
            this.ctx.moveTo(vfX + vfW - cornerLen, vfY);
            this.ctx.lineTo(vfX + vfW, vfY);
            this.ctx.lineTo(vfX + vfW, vfY + cornerLen);
            // Bottom-left
            this.ctx.moveTo(vfX, vfY + vfH - cornerLen);
            this.ctx.lineTo(vfX, vfY + vfH);
            this.ctx.lineTo(vfX + cornerLen, vfY + vfH);
            // Bottom-right
            this.ctx.moveTo(vfX + vfW - cornerLen, vfY + vfH);
            this.ctx.lineTo(vfX + vfW, vfY + vfH);
            this.ctx.lineTo(vfX + vfW, vfY + vfH - cornerLen);
            this.ctx.stroke();
        }
    }
}

window.MiniMap = MiniMap;
