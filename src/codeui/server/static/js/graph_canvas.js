/**
 * High performance HTML5 2D Canvas Graph Engine with multi-layout algorithms,
 * neighborhood isolation, path tracing, cluster hulls, and fluid transitions.
 */
class GraphCanvas {
    constructor(canvasId, isMain = false) {
        this.canvas = typeof canvasId === "string" ? document.getElementById(canvasId) : canvasId;
        if (!this.canvas) {
            console.warn(`GraphCanvas: Canvas element '${canvasId}' not found.`);
            return;
        }
        this.ctx = this.canvas.getContext("2d");
        if (!this.ctx) {
            console.warn(`GraphCanvas: Unable to obtain 2D context for '${canvasId}'.`);
            return;
        }
        this.isMain = isMain;
        this.nodes = [];
        this.links = [];
        this.transform = { x: 0, y: 0, k: 1 };
        this.isInteractive = true;
        this.dragNode = null;
        this.hoverNode = null;
        this.isPanning = false;
        this.dragStartPos = null;
        this.lastMouse = { x: 0, y: 0 };
        this.charge = -250;
        this.alpha = 1.0;
        this.isRunning = true;
        this.animFrameId = null;
        this.animatingLayout = false;
        this.pulsePhase = 0;

        this.touchStartDist = 0;
        this.touchStartScale = 1;
        this.touchStartCenter = { x: 0, y: 0 };
        this.touchStartPos = null;
        this.lastTouchEndTime = 0;

        this.setupCanvas();
        this.setupEvents();
        this.miniMap = isMain ? new MiniMap(this) : null;
        this.startLoop();
    }

    setupCanvas() {
        if (!this.canvas) return;
        this.resizeListener = () => {
            const parent = this.canvas.parentElement;
            const rect = parent ? parent.getBoundingClientRect() : null;
            const w = Math.max(100, Math.floor(rect && rect.width > 0 ? rect.width : (this.canvas.clientWidth || window.innerWidth)));
            const h = Math.max(100, Math.floor(rect && rect.height > 0 ? rect.height : (this.canvas.clientHeight || window.innerHeight)));
            this.canvas.width = w * window.devicePixelRatio;
            this.canvas.height = h * window.devicePixelRatio;
            this.ctx.setTransform(1, 0, 0, 1, 0, 0);
            this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
            if (this.miniMap) this.miniMap.update();
        };
        window.addEventListener("resize", this.resizeListener);
        this.resizeListener();
    }

    handleResize() {
        if (typeof this.resizeListener === "function") {
            this.resizeListener();
        }
    }

    selectAndCenterNode(nodeId) {
        if (!nodeId || !this.nodes) return;
        const node = this.nodes.find(n => n.id === nodeId);
        if (node) {
            if (typeof this.isolateNeighborhood === "function") {
                this.isolateNeighborhood(node.id);
            }
            this.smoothPanZoomTo(node.x, node.y, 1.8);
        }
    }

    destroy() {
        this.isRunning = false;
        if (this.animFrameId) {
            cancelAnimationFrame(this.animFrameId);
            this.animFrameId = null;
        }
        if (this.resizeListener) {
            window.removeEventListener("resize", this.resizeListener);
        }
        if (this.onWindowMouseUp) {
            window.removeEventListener("mouseup", this.onWindowMouseUp);
        }
    }

    setData(nodes, links) {
        if (!this.canvas || !this.ctx) return;
        const nodeMap = new Map();
        const existingMap = new Map((this.nodes || []).map(n => [n.id, n]));

        const w = (this.canvas.width / window.devicePixelRatio) || 800;
        const h = (this.canvas.height / window.devicePixelRatio) || 600;
        const cx = w / 2;
        const cy = h / 2;

        this.nodes = (nodes || []).map((n, index) => {
            const existing = existingMap.get(n.id);
            let initX = existing && isFinite(existing.x) ? existing.x : null;
            let initY = existing && isFinite(existing.y) ? existing.y : null;

            if (initX === null || initY === null) {
                // Golden spiral distribution to prevent node overlap & zero-distance divide
                const angle = index * 2.399963;
                const radius = 22 * Math.sqrt(index + 1);
                initX = cx + Math.cos(angle) * radius + (Math.random() - 0.5) * 8;
                initY = cy + Math.sin(angle) * radius + (Math.random() - 0.5) * 8;
            }

            const node = {
                ...n,
                x: initX,
                y: initY,
                vx: 0,
                vy: 0,
                radius: n.radius || (appState.graphMode === "files" ? 8 : 6)
            };
            nodeMap.set(n.id, node);
            return node;
        });

        this.links = [];
        (links || []).forEach(l => {
            const src = typeof l.source === "object" ? l.source : nodeMap.get(l.source);
            const tgt = typeof l.target === "object" ? l.target : nodeMap.get(l.target);
            if (src && tgt && src !== tgt) {
                this.links.push({
                    source: src,
                    target: tgt,
                    weight: l.weight || 1,
                    kind: l.kind || "imports"
                });
            }
        });

        if (!this.isMain) {
            this.computeSubgraphLayout();
            this.alpha = 0.18;
            setTimeout(() => {
                if (this.canvas) this.fitToScreen();
            }, 60);
        } else if (appState.layoutMode !== "force") {
            this.computeLayout(appState.layoutMode, false);
        } else {
            this.alpha = 1.0;
        }

        if (this.miniMap) this.miniMap.update();
    }

    computeSubgraphLayout() {
        if (!this.nodes || this.nodes.length === 0) return;
        const w = (this.canvas.width / window.devicePixelRatio) || 500;
        const h = (this.canvas.height / window.devicePixelRatio) || 350;
        const cx = w / 2;
        const cy = h / 2;

        const count = this.nodes.length;
        if (count === 1) {
            this.nodes[0].x = cx;
            this.nodes[0].y = cy;
            this.nodes[0].vx = 0;
            this.nodes[0].vy = 0;
            this.fitToScreen();
            return;
        }

        const localNodes = this.nodes.filter(n => !n.isExternal);
        const externalNodes = this.nodes.filter(n => n.isExternal);

        if (externalNodes.length > 0 && localNodes.length > 0) {
            const incomingIds = new Set(this.links.filter(l => l.target && !l.target.isExternal && l.source && l.source.isExternal).map(l => l.source.id));
            const outgoingIds = new Set(this.links.filter(l => l.source && !l.source.isExternal && l.target && l.target.isExternal).map(l => l.target.id));

            const incomingNodes = externalNodes.filter(n => incomingIds.has(n.id));
            const outgoingNodes = externalNodes.filter(n => outgoingIds.has(n.id) && !incomingIds.has(n.id));
            const otherExtNodes = externalNodes.filter(n => !incomingIds.has(n.id) && !outgoingIds.has(n.id));

            const localCount = localNodes.length;
            const localRadius = Math.max(45, Math.min(w * 0.22, h * 0.26, 40 + localCount * 12));
            localNodes.forEach((node, i) => {
                const angle = (i / Math.max(1, localCount)) * Math.PI * 2 - Math.PI / 2;
                node.x = cx + Math.cos(angle) * localRadius;
                node.y = cy + Math.sin(angle) * localRadius;
                node.vx = 0;
                node.vy = 0;
            });

            const inCount = incomingNodes.length;
            if (inCount > 0) {
                const inSpacing = Math.max(32, Math.min(48, (h - 40) / Math.max(1, inCount)));
                const inStartY = cy - ((inCount - 1) * inSpacing) / 2;
                const inX = Math.max(45, cx - localRadius - 65);
                incomingNodes.forEach((node, i) => {
                    node.x = inX;
                    node.y = inStartY + i * inSpacing;
                    node.vx = 0;
                    node.vy = 0;
                });
            }

            const allOut = [...outgoingNodes, ...otherExtNodes];
            const outCount = allOut.length;
            if (outCount > 0) {
                const outSpacing = Math.max(32, Math.min(48, (h - 40) / Math.max(1, outCount)));
                const outStartY = cy - ((outCount - 1) * outSpacing) / 2;
                const outX = Math.min(w - 45, cx + localRadius + 65);
                allOut.forEach((node, i) => {
                    node.x = outX;
                    node.y = outStartY + i * outSpacing;
                    node.vx = 0;
                    node.vy = 0;
                });
            }

            this.fitToScreen();
            return;
        }

        const classes = this.nodes.filter(n => n.kind === "class" || n.kind === "interface" || n.kind === "struct");
        const functions = this.nodes.filter(n => n.kind === "function" || n.kind === "method");
        const variables = this.nodes.filter(n => n.kind === "variable" || n.kind === "constant" || n.kind === "property" || n.kind === "type_alias");
        const others = this.nodes.filter(n => !classes.includes(n) && !functions.includes(n) && !variables.includes(n));

        if (classes.length > 0) {
            const rows = [classes, functions, [...variables, ...others]].filter(r => r.length > 0);
            const rowHeight = Math.min(110, (h - 80) / Math.max(1, rows.length));
            const startY = cy - ((rows.length - 1) * rowHeight) / 2;

            rows.forEach((row, rIdx) => {
                const y = startY + rIdx * rowHeight;
                const rowCount = row.length;
                const spacing = Math.min(140, (w - 80) / Math.max(1, rowCount));
                const startX = cx - ((rowCount - 1) * spacing) / 2;
                row.forEach((node, idx) => {
                    node.x = startX + idx * spacing;
                    node.y = y;
                    node.vx = 0;
                    node.vy = 0;
                });
            });
        } else {
            const radius = Math.min(w * 0.35, h * 0.35, 45 + count * 15);
            this.nodes.forEach((node, i) => {
                const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
                node.x = cx + Math.cos(angle) * radius;
                node.y = cy + Math.sin(angle) * radius;
                node.vx = 0;
                node.vy = 0;
            });
        }
        this.fitToScreen();
    }

    setupEvents() {
        const getPos = e => {
            const rect = this.canvas.getBoundingClientRect();
            return {
                x: (e.clientX - rect.left - this.transform.x) / this.transform.k,
                y: (e.clientY - rect.top - this.transform.y) / this.transform.k,
                rawX: e.clientX - rect.left,
                rawY: e.clientY - rect.top,
                screenX: e.clientX,
                screenY: e.clientY
            };
        };

        const findNode = (x, y) => {
            for (let i = this.nodes.length - 1; i >= 0; i--) {
                const n = this.nodes[i];
                const dx = n.x - x;
                const dy = n.y - y;
                const hitRadius = (n.radius || 8) + 8;
                if (dx * dx + dy * dy < hitRadius * hitRadius) return n;
            }
            return null;
        };

        this.canvas.addEventListener("mousedown", e => {
            if (this.isMain && this.isInteractive === false) return;
            const pos = getPos(e);
            this.dragNode = findNode(pos.x, pos.y);
            this.dragStartPos = { x: pos.x, y: pos.y, screenX: e.clientX, screenY: e.clientY };
            this.hasMovedDrag = false;
            if (this.dragNode) {
                this.dragNode.fx = this.dragNode.x;
                this.dragNode.fy = this.dragNode.y;
            } else {
                this.isPanning = true;
                this.lastMouse = { x: pos.rawX, y: pos.rawY };
            }
        });

        this.canvas.addEventListener("mousemove", e => {
            if (this.isMain && this.isInteractive === false) return;
            const pos = getPos(e);
            if (this.dragNode) {
                const startX = this.dragStartPos ? this.dragStartPos.screenX : e.clientX;
                const startY = this.dragStartPos ? this.dragStartPos.screenY : e.clientY;
                const dist = Math.hypot(e.clientX - startX, e.clientY - startY);
                if (dist > 6) {
                    this.hasMovedDrag = true;
                    this.dragNode.fx = pos.x;
                    this.dragNode.fy = pos.y;
                    this.dragNode.x = pos.x;
                    this.dragNode.y = pos.y;
                    this.dragNode.vx = 0;
                    this.dragNode.vy = 0;
                    if (!this.isMain || appState.layoutMode === "force") {
                        this.alpha = Math.max(this.alpha, 0.25);
                    }
                }
            } else if (this.isPanning) {
                const startX = this.dragStartPos ? this.dragStartPos.screenX : (this.lastMouse ? this.lastMouse.x : e.clientX);
                const startY = this.dragStartPos ? this.dragStartPos.screenY : (this.lastMouse ? this.lastMouse.y : e.clientY);
                const dist = Math.hypot(e.clientX - startX, e.clientY - startY);
                if (dist > 6) {
                    this.hasMovedDrag = true;
                }
                const prevX = this.lastMouse ? this.lastMouse.x : pos.rawX;
                const prevY = this.lastMouse ? this.lastMouse.y : pos.rawY;
                this.transform.x += pos.rawX - prevX;
                this.transform.y += pos.rawY - prevY;
                this.lastMouse = { x: pos.rawX, y: pos.rawY };
                if (this.miniMap) this.miniMap.update();
            } else {
                const prevHover = this.hoverNode;
                this.hoverNode = findNode(pos.x, pos.y);
                this.canvas.style.cursor = this.hoverNode ? "pointer" : "grab";
                if (this.hoverNode !== prevHover) {
                    this.updateHoverTooltip(this.hoverNode, pos.screenX, pos.screenY);
                }
            }
        });

        this.canvas.addEventListener("mouseleave", () => {
            this.hoverNode = null;
            this.hideHoverTooltip();
        });

        this.onWindowMouseUp = () => {
            if (this.dragNode) {
                this.dragNode.fx = null;
                this.dragNode.fy = null;
                this.dragNode.vx = 0;
                this.dragNode.vy = 0;
                this.dragNode = null;
                if (!this.isMain || appState.layoutMode === "force") {
                    this.alpha = Math.max(this.alpha, 0.2);
                }
            }
            this.isPanning = false;
            this.dragStartPos = null;
        };
        window.addEventListener("mouseup", this.onWindowMouseUp);

        const handleNodeActivation = (node, isDoubleClick = false) => {
            if (!node) return;
            if (this.isMain) {
                if (appState.tracerActive) {
                    App.handleTracerNodeClick(node.id);
                    return;
                }

                appState.selectedFileNodeId = node.id;
                this.isolateNeighborhood(node.id);
                Sidebar.highlightSelectedCard(node.id);

                const isSymbolNode = appState.graphMode === "symbols" ||
                                     node.type === "symbol" ||
                                     Boolean(node.rawSymbol) ||
                                     (typeof node.id === "string" && node.id.includes("::"));

                let targetFile = appState.graphMode === "files" ? node.id : (node.fileId || (typeof node.id === "string" ? node.id.split("::")[0] : ""));
                let targetSymbol = isSymbolNode ? node.id : null;
                if (node.rawSymbol && node.rawSymbol.location && node.rawSymbol.location.file_id) {
                    targetFile = node.rawSymbol.location.file_id;
                    targetSymbol = node.rawSymbol.id;
                }

                if (isDoubleClick) {
                    SubGraphManager.openWindow(targetFile, targetSymbol, null, "", "graph");
                }
            } else {
                this.selectedNodeId = node.id;
                this.isolateNeighborhood(node.id);
                if (isDoubleClick && this.onNodeDoubleClick) {
                    this.onNodeDoubleClick(node);
                } else if (this.onNodeSelected) {
                    this.onNodeSelected(node);
                }
            }
        };

        const handleEmptyCanvasClick = () => {
            this.hasMovedDrag = false;
            this.hoverNode = null;
            this.hideHoverTooltip();
            this.clearNeighborhoodIsolation();
            if (this.isMain) {
                Sidebar.clearSelection();
                if (!appState.tracerActive) {
                    App.hideNodeHUD();
                }
            } else if (this.onEmptyCanvasClick) {
                this.onEmptyCanvasClick();
            }
        };

        let lastClickTime = 0;
        let lastClickNodeId = null;
        let lastDblClickTime = 0;

        this.canvas.addEventListener("click", e => {
            if (this.isMain && this.isInteractive === false) return;
            if (this.lastTouchEndTime && (Date.now() - this.lastTouchEndTime < 450)) {
                return;
            }
            if (this.hasMovedDrag) {
                this.hasMovedDrag = false;
                return;
            }
            const pos = getPos(e);
            const node = findNode(pos.x, pos.y);
            const now = Date.now();

            if (node) {
                const timeDiff = now - lastClickTime;
                const isSlowDblClick = (lastClickNodeId === node.id) && (timeDiff < 650);

                if (isSlowDblClick) {
                    lastClickTime = 0;
                    lastClickNodeId = null;
                    lastDblClickTime = now;
                    handleNodeActivation(node, true);
                } else {
                    lastClickTime = now;
                    lastClickNodeId = node.id;
                    handleNodeActivation(node, false);
                }
            } else {
                lastClickTime = 0;
                lastClickNodeId = null;
                handleEmptyCanvasClick();
            }
            this.lastClickedNodeId = node?.id || null;
        });

        this.canvas.addEventListener("dblclick", e => {
            if (this.isMain && this.isInteractive === false) return;
            if (this.hasMovedDrag) return;
            const now = Date.now();
            if (now - lastDblClickTime < 450) {
                return;
            }
            const pos = getPos(e);
            const node = findNode(pos.x, pos.y);
            if (node) {
                lastDblClickTime = now;
                lastClickTime = 0;
                lastClickNodeId = null;
                handleNodeActivation(node, true);
            }
        });

        this.canvas.addEventListener("wheel", e => {
            if (this.isMain && this.isInteractive === false) return;
            e.preventDefault();
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            const zoomFactor = e.deltaY < 0 ? 1.12 : 0.88;
            const newK = Math.max(0.05, Math.min(10, this.transform.k * zoomFactor));

            this.transform.x = mouseX - (mouseX - this.transform.x) * (newK / this.transform.k);
            this.transform.y = mouseY - (mouseY - this.transform.y) * (newK / this.transform.k);
            this.transform.k = newK;
            if (this.miniMap) this.miniMap.update();
        }, { passive: false });

        this.canvas.addEventListener("touchstart", e => {
            if (this.isMain && this.isInteractive === false) return;
            if (e.touches.length === 1) {
                const rect = this.canvas.getBoundingClientRect();
                const rawX = e.touches[0].clientX - rect.left;
                const rawY = e.touches[0].clientY - rect.top;
                const worldX = (rawX - this.transform.x) / this.transform.k;
                const worldY = (rawY - this.transform.y) / this.transform.k;
                this.dragNode = findNode(worldX, worldY);
                this.touchStartPos = { x: worldX, y: worldY, rawX, rawY, screenX: e.touches[0].clientX, screenY: e.touches[0].clientY };
                this.hasMovedDrag = false;
                if (this.dragNode) {
                    this.dragNode.fx = this.dragNode.x;
                    this.dragNode.fy = this.dragNode.y;
                } else {
                    this.isPanning = true;
                    this.lastMouse = { x: rawX, y: rawY };
                }
            } else if (e.touches.length === 2) {
                e.preventDefault();
                const rect = this.canvas.getBoundingClientRect();
                const t1 = e.touches[0];
                const t2 = e.touches[1];
                this.touchStartDist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
                this.touchStartScale = this.transform.k;
                this.touchStartCenter = {
                    x: (t1.clientX + t2.clientX) / 2 - rect.left,
                    y: (t1.clientY + t2.clientY) / 2 - rect.top
                };
            }
        }, { passive: false });

        this.canvas.addEventListener("touchmove", e => {
            if (this.isMain && this.isInteractive === false) return;
            if (e.cancelable && (this.isPanning || this.dragNode || e.touches.length > 1)) {
                e.preventDefault();
            }
            if (e.touches.length === 1) {
                const rect = this.canvas.getBoundingClientRect();
                const rawX = e.touches[0].clientX - rect.left;
                const rawY = e.touches[0].clientY - rect.top;
                const worldX = (rawX - this.transform.x) / this.transform.k;
                const worldY = (rawY - this.transform.y) / this.transform.k;
                const dist = Math.hypot(e.touches[0].clientX - (this.touchStartPos ? this.touchStartPos.screenX : rawX), e.touches[0].clientY - (this.touchStartPos ? this.touchStartPos.screenY : rawY));
                if (dist > 6) {
                    this.hasMovedDrag = true;
                }
                if (this.dragNode) {
                    if (this.hasMovedDrag) {
                        this.dragNode.fx = worldX;
                        this.dragNode.fy = worldY;
                        this.dragNode.x = worldX;
                        this.dragNode.y = worldY;
                        this.dragNode.vx = 0;
                        this.dragNode.vy = 0;
                    }
                } else if (this.isPanning) {
                    this.transform.x += rawX - this.lastMouse.x;
                    this.transform.y += rawY - this.lastMouse.y;
                    this.lastMouse = { x: rawX, y: rawY };
                    if (this.miniMap) this.miniMap.update();
                }
            } else if (e.touches.length === 2) {
                e.preventDefault();
                const rect = this.canvas.getBoundingClientRect();
                const t1 = e.touches[0];
                const t2 = e.touches[1];
                const currentDist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
                if (this.touchStartDist > 0) {
                    const factor = currentDist / this.touchStartDist;
                    const newK = Math.max(0.05, Math.min(10, this.touchStartScale * factor));
                    const cx = this.touchStartCenter.x;
                    const cy = this.touchStartCenter.y;
                    this.transform.x = cx - (cx - this.transform.x) * (newK / this.transform.k);
                    this.transform.y = cy - (cy - this.transform.y) * (newK / this.transform.k);
                    this.transform.k = newK;
                    if (this.miniMap) this.miniMap.update();
                }
            }
        }, { passive: false });

        this.canvas.addEventListener("touchend", () => {
            this.lastTouchEndTime = Date.now();
            if (this.dragNode) {
                this.dragNode.fx = null;
                this.dragNode.fy = null;
                this.dragNode.vx = 0;
                this.dragNode.vy = 0;
                this.dragNode = null;
            }
            this.isPanning = false;
            if (!this.hasMovedDrag && this.touchStartPos) {
                const node = findNode(this.touchStartPos.x, this.touchStartPos.y);
                const now = Date.now();
                if (node) {
                    const timeDiff = now - lastClickTime;
                    const isSlowDblClick = (lastClickNodeId === node.id) && (timeDiff < 650);
                    if (isSlowDblClick) {
                        lastClickTime = 0;
                        lastClickNodeId = null;
                        lastDblClickTime = now;
                        handleNodeActivation(node, true);
                    } else {
                        lastClickTime = now;
                        lastClickNodeId = node.id;
                        handleNodeActivation(node, false);
                    }
                } else {
                    lastClickTime = 0;
                    lastClickNodeId = null;
                    handleEmptyCanvasClick();
                }
                this.lastClickedNodeId = node?.id || null;
            }
            this.touchStartDist = 0;
            this.touchStartPos = null;
        });

        this.canvas.addEventListener("touchcancel", () => {
            if (this.dragNode) {
                this.dragNode.fx = null;
                this.dragNode.fy = null;
                this.dragNode.vx = 0;
                this.dragNode.vy = 0;
                this.dragNode = null;
            }
            this.isPanning = false;
            this.touchStartDist = 0;
            this.touchStartPos = null;
        });
    }

    setCharge(val) {
        this.charge = parseFloat(val);
        if (this.isMain && appState.layoutMode === "force") {
            this.alpha = 0.4;
        }
    }

    setLayout(layoutName) {
        appState.layoutMode = layoutName;
        if (layoutName === "force") {
            this.alpha = 1.0;
            this.isRunning = true;
        } else {
            this.computeLayout(layoutName, true);
        }
    }

    computeLayout(layoutName, animate = true) {
        if (!this.nodes || this.nodes.length === 0) return;
        const w = this.canvas.width / window.devicePixelRatio;
        const h = this.canvas.height / window.devicePixelRatio;
        const cx = w / 2;
        const cy = h / 2;

        const targets = new Map();

        if (layoutName === "hierarchical") {
            const layerOrder = { entry: 0, frontend: 1, backend: 2, shared: 3, test: 4, config: 4, other: 3 };
            const groups = new Map();
            this.nodes.forEach(n => {
                const layer = n.layer || "other";
                const rank = layerOrder[layer] !== undefined ? layerOrder[layer] : 3;
                if (!groups.has(rank)) groups.set(rank, []);
                groups.get(rank).push(n);
            });

            const sortedRanks = Array.from(groups.keys()).sort((a, b) => a - b);
            let currentY = 80;

            sortedRanks.forEach((rank) => {
                const rowNodes = groups.get(rank) || [];
                const maxPerSubRow = 6;
                const subRows = Math.ceil(rowNodes.length / maxPerSubRow);
                const spacing = 120;

                for (let sr = 0; sr < subRows; sr++) {
                    const slice = rowNodes.slice(sr * maxPerSubRow, (sr + 1) * maxPerSubRow);
                    const itemsInSubRow = slice.length;
                    const startX = cx - ((itemsInSubRow - 1) * spacing) / 2;
                    slice.forEach((node, idx) => {
                        targets.set(node.id, { x: startX + idx * spacing, y: currentY });
                    });
                    currentY += 75;
                }
                currentY += 45;
            });
        } else if (layoutName === "radial") {
            const layerRings = { entry: 0, frontend: 1, backend: 1, shared: 2, other: 2, test: 3, config: 3 };
            const rings = new Map();
            this.nodes.forEach(n => {
                const ring = layerRings[n.layer] || 2;
                if (!rings.has(ring)) rings.set(ring, []);
                rings.get(ring).push(n);
            });

            rings.forEach((ringNodes, ringIdx) => {
                const count = ringNodes.length;
                const radius = ringIdx === 0 ? (count === 1 ? 0 : 65) : (100 + ringIdx * 125 + Math.min(180, count * 6));
                ringNodes.forEach((node, i) => {
                    const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
                    targets.set(node.id, { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius });
                });
            });
        } else if (layoutName === "clusters") {
            if (this.isMain && appState.graphMode === "symbols") {
                // Hierarchical clustering: Main Folder -> Subfolder -> File Subcluster -> Symbols
                const hierarchy = new Map();
                this.nodes.forEach(n => {
                    const mf = n.mainFolder || "root";
                    const sf = n.subfolder || "root";
                    const fid = n.fileId || "root";
                    if (!hierarchy.has(mf)) hierarchy.set(mf, new Map());
                    const subMap = hierarchy.get(mf);
                    if (!subMap.has(sf)) subMap.set(sf, new Map());
                    const fileMap = subMap.get(sf);
                    if (!fileMap.has(fid)) fileMap.set(fid, []);
                    fileMap.get(fid).push(n);
                });

                const mainFolders = Array.from(hierarchy.keys());
                const mfCount = mainFolders.length;
                const mfRadius = Math.max(220, Math.min(w, h) * 0.44 + mfCount * 28);

                mainFolders.forEach((mf, mfIdx) => {
                    const mfAngle = (mfIdx / Math.max(1, mfCount)) * Math.PI * 2 - Math.PI / 2;
                    const mfX = cx + Math.cos(mfAngle) * mfRadius;
                    const mfY = cy + Math.sin(mfAngle) * mfRadius;

                    const subMap = hierarchy.get(mf);
                    const subfolders = Array.from(subMap.keys());
                    const sfCount = subfolders.length;
                    const sfRadius = Math.max(110, Math.sqrt(sfCount) * 80);

                    subfolders.forEach((sf, sfIdx) => {
                        const sfAngle = (sfIdx / Math.max(1, sfCount)) * Math.PI * 2;
                        const sfX = mfX + Math.cos(sfAngle) * sfRadius;
                        const sfY = mfY + Math.sin(sfAngle) * sfRadius;

                        const fileMap = subMap.get(sf);
                        const files = Array.from(fileMap.keys());
                        const fileCount = files.length;
                        const fileRadius = Math.max(70, Math.sqrt(fileCount) * 60);

                        files.forEach((fid, fIdx) => {
                            const fAngle = (fIdx / Math.max(1, fileCount)) * Math.PI * 2;
                            const fileX = sfX + Math.cos(fAngle) * fileRadius;
                            const fileY = sfY + Math.sin(fAngle) * fileRadius;

                            const symNodes = fileMap.get(fid) || [];
                            const symCount = symNodes.length;
                            const symRadius = symCount <= 1 ? 0 : Math.max(45, 28 + symCount * 12);

                            symNodes.forEach((node, sIdx) => {
                                const sAngle = (sIdx / Math.max(1, symCount)) * Math.PI * 2;
                                targets.set(node.id, {
                                    x: fileX + Math.cos(sAngle) * symRadius,
                                    y: fileY + Math.sin(sAngle) * symRadius
                                });
                            });
                        });
                    });
                });
            } else {
                const clusters = new Map();
                this.nodes.forEach(n => {
                    const feat = n.feature || "root";
                    if (!clusters.has(feat)) clusters.set(feat, []);
                    clusters.get(feat).push(n);
                });

                const featKeys = Array.from(clusters.keys());
                const clusterCount = featKeys.length;
                const clusterRadius = Math.max(140, Math.min(w, h) * 0.38 + clusterCount * 12);

                featKeys.forEach((feat, cIdx) => {
                    const clusterAngle = (cIdx / clusterCount) * Math.PI * 2 - Math.PI / 2;
                    const clusterX = cx + Math.cos(clusterAngle) * clusterRadius;
                    const clusterY = cy + Math.sin(clusterAngle) * clusterRadius;
                    const cNodes = clusters.get(feat);
                    const subCount = cNodes.length;
                    const subRadius = Math.max(50, Math.sqrt(subCount) * 30);

                    cNodes.forEach((node, sIdx) => {
                        const subAngle = (sIdx / subCount) * Math.PI * 2;
                        targets.set(node.id, {
                            x: clusterX + Math.cos(subAngle) * subRadius,
                            y: clusterY + Math.sin(subAngle) * subRadius
                        });
                    });
                });
            }
        }

        if (animate) {
            this.animateToPositions(targets);
        } else {
            this.nodes.forEach(n => {
                const t = targets.get(n.id);
                if (t) {
                    n.x = t.x;
                    n.y = t.y;
                    n.vx = 0;
                    n.vy = 0;
                }
            });
            this.fitToScreen();
        }
    }

    animateToPositions(targets) {
        this.animatingLayout = true;
        const startPos = new Map(this.nodes.map(n => [n.id, { x: n.x, y: n.y }]));
        const duration = 380;
        const startTime = performance.now();

        const step = now => {
            const progress = Math.min(1, (now - startTime) / duration);
            const ease = progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(-2 * progress + 2, 3) / 2;

            this.nodes.forEach(n => {
                const start = startPos.get(n.id);
                const tgt = targets.get(n.id);
                if (start && tgt) {
                    n.x = start.x + (tgt.x - start.x) * ease;
                    n.y = start.y + (tgt.y - start.y) * ease;
                    n.vx = 0;
                    n.vy = 0;
                }
            });

            if (this.miniMap) this.miniMap.update();

            if (progress < 1) {
                requestAnimationFrame(step);
            } else {
                this.animatingLayout = false;
                this.fitToScreen();
            }
        };
        requestAnimationFrame(step);
    }

    isolateNeighborhood(target, maxDepth = 10) {
        if (!target) return;
        const nodeId = typeof target === "object" ? target.id : target;
        if (!nodeId) return;

        const reachable = new Map();
        reachable.set(nodeId, { depth: 0, direction: "root" });

        const forwardAdj = new Map();
        const reverseAdj = new Map();

        this.links.forEach(l => {
            const s = typeof l.source === "object" ? l.source.id : l.source;
            const t = typeof l.target === "object" ? l.target.id : l.target;
            if (!s || !t) return;
            if (!forwardAdj.has(s)) forwardAdj.set(s, []);
            forwardAdj.get(s).push(t);

            if (!reverseAdj.has(t)) reverseAdj.set(t, []);
            reverseAdj.get(t).push(s);
        });

        const forwardQueue = [{ id: nodeId, depth: 0 }];
        while (forwardQueue.length > 0) {
            const curr = forwardQueue.shift();
            if (curr.depth >= maxDepth) continue;
            const neighbors = forwardAdj.get(curr.id) || [];
            for (const next of neighbors) {
                if (!reachable.has(next)) {
                    reachable.set(next, { depth: curr.depth + 1, direction: "downstream" });
                    forwardQueue.push({ id: next, depth: curr.depth + 1 });
                }
            }
        }

        const reverseQueue = [{ id: nodeId, depth: 0 }];
        while (reverseQueue.length > 0) {
            const curr = reverseQueue.shift();
            if (curr.depth >= maxDepth) continue;
            const neighbors = reverseAdj.get(curr.id) || [];
            for (const next of neighbors) {
                if (!reachable.has(next)) {
                    reachable.set(next, { depth: curr.depth + 1, direction: "upstream" });
                    reverseQueue.push({ id: next, depth: curr.depth + 1 });
                }
            }
        }

        this.focusedNeighborhood = reachable;
        this.selectedNodeId = nodeId;
        if (this.isMain) {
            appState.focusedNeighborhood = reachable;
        }
    }

    clearNeighborhoodIsolation() {
        this.focusedNeighborhood = null;
        this.selectedNodeId = null;
        if (this.isMain) {
            appState.focusedNeighborhood = null;
            appState.selectedFileNodeId = null;
        }
        this.lastClickedNodeId = null;
    }

    smoothPanZoomTo(worldX, worldY, targetK = 1.8) {
        const w = this.canvas.width / window.devicePixelRatio;
        const h = this.canvas.height / window.devicePixelRatio;
        const startX = this.transform.x;
        const startY = this.transform.y;
        const startK = this.transform.k;

        const endX = w / 2 - worldX * targetK;
        const endY = h / 2 - worldY * targetK;
        const duration = 400;
        const startTime = performance.now();

        const step = now => {
            const p = Math.min(1, (now - startTime) / duration);
            const ease = 1 - Math.pow(1 - p, 3);
            this.transform.x = startX + (endX - startX) * ease;
            this.transform.y = startY + (endY - startY) * ease;
            this.transform.k = startK + (targetK - startK) * ease;
            if (this.miniMap) this.miniMap.update();
            if (p < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    }

    updateHoverTooltip(node, screenX, screenY) {
        let tooltip = document.getElementById("canvas-node-tooltip");
        if (!tooltip) {
            tooltip = document.createElement("div");
            tooltip.id = "canvas-node-tooltip";
            tooltip.className = "canvas-tooltip";
            document.body.appendChild(tooltip);
        }

        if (!node) {
            tooltip.style.display = "none";
            return;
        }

        const callers = this.links.filter(l => l.target === node).length;
        const callees = this.links.filter(l => l.source === node).length;

        let extBadge = "";
        if (node.isExternal) {
            extBadge = `<div style="font-size:0.65rem; color:#c084fc; font-weight:700; margin-bottom:2px;">🌐 External Cross-File Node</div>`;
        }

        let kindBadge = "";
        if (node.isLoneFile || node.kind === "file") {
            kindBadge = `<span class="badge" style="background:#475569; color:#f1f5f9;">FILE</span>`;
        } else if (node.kind) {
            kindBadge = `<span class="badge" style="background:var(--accent); color:#ffffff;">${node.kind.toUpperCase()}</span>`;
        }

        tooltip.innerHTML = `
            ${extBadge}
            <div style="font-weight:700; color:var(--text-main); display:flex; align-items:center; gap:6px;">
                <span>${node.label}</span>
                ${kindBadge}
            </div>
            <div style="font-size:0.68rem; color:var(--text-muted); margin-bottom:4px;">${node.id}</div>
            <div style="display:flex; gap:6px; font-size:0.68rem;">
                <span class="badge ${node.layer || 'shared'}">${node.layer || 'other'}</span>
                <span style="color:var(--text-dim);">In: ${callers} · Out: ${callees}</span>
            </div>
            ${node.isExternal && node.fileId ? `<div style="font-size:0.64rem; color:var(--accent); margin-top:4px;">Double-click to open ${node.fileId.split('/').pop()}</div>` : ''}
        `;
        if (typeof screenX === "number" && typeof screenY === "number") {
            tooltip.style.left = `${screenX + 14}px`;
            tooltip.style.top = `${screenY + 14}px`;
        }
        tooltip.style.display = "block";
    }

    hideHoverTooltip() {
        const tooltip = document.getElementById("canvas-node-tooltip");
        if (tooltip) tooltip.style.display = "none";
    }

    startLoop() {
        this.isRunning = true;
        const step = () => {
            if (!this.isRunning) return;
            this.pulsePhase = (this.pulsePhase + 0.04) % (Math.PI * 2);
            if (!this.animatingLayout) {
                if (this.isMain) {
                    if (appState.layoutMode === "force") this.updatePhysics();
                } else {
                    this.updatePhysics();
                }
            }
            this.render();
            this.animFrameId = requestAnimationFrame(step);
        };
        this.animFrameId = requestAnimationFrame(step);
    }

    updatePhysics() {
        if (this.alpha < 0.003 || !this.nodes || this.nodes.length === 0) return;
        if (this.isMain && appState.layoutMode !== "force") return;
        this.alpha *= 0.965;
        if (this.alpha < 0.003) {
            this.alpha = 0;
            return;
        }

        const count = this.nodes.length;
        const isSymMode = this.isMain && appState.graphMode === "symbols";
        const repulsionStrength = !this.isMain ? 650 : (Math.abs(this.charge || (isSymMode ? 340 : 250)) * (isSymMode ? 22 : 16));
        const maxPhysicsNodes = Math.min(count, 350);

        // 1. Coulomb Repulsion with distance threshold & node capping for fluid 60FPS
        for (let i = 0; i < maxPhysicsNodes; i++) {
            const n1 = this.nodes[i];
            for (let j = i + 1; j < maxPhysicsNodes; j++) {
                const n2 = this.nodes[j];
                let dx = n2.x - n1.x;
                let dy = n2.y - n1.y;
                if (Math.abs(dx) > 600 || Math.abs(dy) > 600) continue;
                if (dx === 0 && dy === 0) {
                    dx = (Math.random() - 0.5) * 2;
                    dy = (Math.random() - 0.5) * 2;
                }
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist > 600) continue;
                const distClamped = Math.max(10, dist);

                const repForce = (repulsionStrength * this.alpha) / (distClamped * distClamped);
                const force = Math.min(35, repForce);
                const fx = (dx / distClamped) * force;
                const fy = (dy / distClamped) * force;

                // Push n1 away from n2 (-fx), and push n2 away from n1 (+fx)
                if (!n1.fx) { n1.vx -= fx; n1.vy -= fy; }
                if (!n2.fx) { n2.vx += fx; n2.vy += fy; }

                // Elastic anti-overlap separation
                const basePadding = !this.isMain ? 18 : (isSymMode ? 64 : 42);
                const minDistance = (n1.radius || 8) + (n2.radius || 8) + basePadding;
                if (dist < minDistance) {
                    const overlap = minDistance - dist;
                    const sepPush = overlap * 0.55 * Math.max(0.35, this.alpha);
                    const sx = (dx / distClamped) * sepPush;
                    const sy = (dy / distClamped) * sepPush;
                    if (!n1.fx) { n1.vx -= sx; n1.vy -= sy; }
                    if (!n2.fx) { n2.vx += sx; n2.vy += sy; }
                }
            }
        }

        // 2. Link spring attraction
        this.links.forEach(l => {
            if (!l.source || !l.target) return;
            let dx = l.target.x - l.source.x;
            let dy = l.target.y - l.source.y;
            if (dx === 0 && dy === 0) {
                dx = (Math.random() - 0.5);
                dy = (Math.random() - 0.5);
            }
            const dist = Math.sqrt(dx * dx + dy * dy);
            const distClamped = Math.max(1, dist);
            const targetDist = !this.isMain ? (this.focusedNeighborhood ? 46 : 58) : (isSymMode ? 120 : 105);
            const rawForce = (distClamped - targetDist) * 0.02 * this.alpha;
            const force = Math.max(-18, Math.min(18, rawForce));
            const fx = (dx / distClamped) * force;
            const fy = (dy / distClamped) * force;

            if (!l.source.fx) { l.source.vx += fx; l.source.vy += fy; }
            if (!l.target.fx) { l.target.vx -= fx; l.target.vy -= fy; }
        });

        // 2b. Hierarchical cluster attraction in symbols mode (pulls symbols toward their file centroid)
        if (this.isMain && appState.graphMode === "symbols" && this.nodes.length > 0) {
            const fileCentroids = new Map();
            this.nodes.forEach(n => {
                const fid = n.fileId || n.folder || "root";
                if (!fileCentroids.has(fid)) {
                    fileCentroids.set(fid, { sumX: 0, sumY: 0, count: 0 });
                }
                const c = fileCentroids.get(fid);
                c.sumX += n.x;
                c.sumY += n.y;
                c.count += 1;
            });

            const clusterPull = 0.00018 * this.alpha;
            this.nodes.forEach(n => {
                if (n.fx) return;
                const fid = n.fileId || n.folder || "root";
                const c = fileCentroids.get(fid);
                if (c && c.count > 1) {
                    const avgX = c.sumX / c.count;
                    const avgY = c.sumY / c.count;
                    n.vx += (avgX - n.x) * clusterPull;
                    n.vy += (avgY - n.y) * clusterPull;
                }
            });
        }

        // 3. Gentle Center Gravity & Velocity Integration
        const w = (this.canvas.width / window.devicePixelRatio) || this.canvas.clientWidth || window.innerWidth;
        const h = (this.canvas.height / window.devicePixelRatio) || this.canvas.clientHeight || window.innerHeight;
        const cx = w / 2;
        const cy = h / 2;
        const maxVelocity = 8;
        const gravityStrength = !this.isMain ? 0.0014 : (this.isMain ? 0.00015 : 0.00035);

        this.nodes.forEach(n => {
            if (!n.fx) {
                n.vx += (cx - n.x) * gravityStrength * this.alpha;
                n.vy += (cy - n.y) * gravityStrength * this.alpha;
                n.vx *= 0.80;
                n.vy *= 0.80;

                const v = Math.hypot(n.vx, n.vy);
                if (v > maxVelocity) {
                    n.vx = (n.vx / v) * maxVelocity;
                    n.vy = (n.vy / v) * maxVelocity;
                }

                if (!isFinite(n.x) || !isFinite(n.y) || isNaN(n.x) || isNaN(n.y)) {
                    n.x = cx + (Math.random() - 0.5) * 100;
                    n.y = cy + (Math.random() - 0.5) * 100;
                    n.vx = 0;
                    n.vy = 0;
                } else {
                    n.x += n.vx;
                    n.y += n.vy;
                }
            }
        });

        if (this.miniMap) {
            this.miniMap.update();
        }
    }

    drawNodePath(n, radiusOffset = 0) {
        const kind = (n.kind || (n.isLoneFile ? "file" : "")).toLowerCase();
        let baseR = n.radius || 8;
        if (!this.isMain && baseR < 10) baseR = 10;
        const r = baseR + radiusOffset;
        this.ctx.beginPath();

        if (kind === "class" || kind === "struct") {
            for (let i = 0; i < 6; i++) {
                const angle = (i * Math.PI) / 3 - Math.PI / 6;
                const px = n.x + r * Math.cos(angle);
                const py = n.y + r * Math.sin(angle);
                if (i === 0) this.ctx.moveTo(px, py);
                else this.ctx.lineTo(px, py);
            }
            this.ctx.closePath();
        } else if (kind === "method") {
            const hr = r * 1.15;
            this.ctx.moveTo(n.x, n.y - hr);
            this.ctx.lineTo(n.x + hr, n.y);
            this.ctx.lineTo(n.x, n.y + hr);
            this.ctx.lineTo(n.x - hr, n.y);
            this.ctx.closePath();
        } else if (kind === "interface" || kind === "enum" || kind === "type_alias" || kind === "type") {
            for (let i = 0; i < 8; i++) {
                const angle = (i * Math.PI) / 4 - Math.PI / 8;
                const px = n.x + r * Math.cos(angle);
                const py = n.y + r * Math.sin(angle);
                if (i === 0) this.ctx.moveTo(px, py);
                else this.ctx.lineTo(px, py);
            }
            this.ctx.closePath();
        } else if (kind === "file" || n.isLoneFile) {
            const w = r * 1.8;
            const h = r * 1.4;
            if (this.ctx.roundRect) {
                this.ctx.roundRect(n.x - w / 2, n.y - h / 2, w, h, 3);
            } else {
                this.ctx.rect(n.x - w / 2, n.y - h / 2, w, h);
            }
            this.ctx.closePath();
        } else if (kind === "variable" || kind === "constant" || kind === "property") {
            const vr = Math.max(3.5, r * 0.7);
            this.ctx.arc(n.x, n.y, vr, 0, Math.PI * 2);
        } else {
            this.ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        }
    }

    render() {
        const w = this.canvas.width / window.devicePixelRatio;
        const h = this.canvas.height / window.devicePixelRatio;
        this.ctx.clearRect(0, 0, w, h);

        this.ctx.save();
        this.ctx.translate(this.transform.x, this.transform.y);
        this.ctx.scale(this.transform.k, this.transform.k);

        const focused = this.isMain ? appState.focusedNeighborhood : this.focusedNeighborhood;
        const selNodeId = this.isMain ? appState.selectedFileNodeId : (this.selectedNodeId || (this.focusedNeighborhood ? this.focusedNeighborhood.keys().next().value : null));
        const unusedNodeIds = appState.unusedHighlightMode ? appState.getUnusedNodeIds() : null;
        const tracePath = appState.activeTracePath || [];
        const isTracePathEdge = (srcId, tgtId) => {
            for (let i = 0; i < tracePath.length - 1; i++) {
                if (tracePath[i] === srcId && tracePath[i + 1] === tgtId) return true;
                if (tracePath[i] === tgtId && tracePath[i + 1] === srcId) return true;
            }
            return false;
        };

        // 1. Draw Cluster Boundaries if enabled
        if (appState.layoutMode === "clusters" && appState.clusterHullsMode) {
            this.renderClusterHulls();
        }

        const themeColors = window.ThemeManager ? window.ThemeManager.getCanvasColors() : {
            nodeText: "#f1f5f9",
            nodeTextDim: "#94a3b8",
            nodeTextExternal: "#e9d5ff",
            nodeTextExternalFile: "#c084fc",
            nodeHoverRing: "#f8fafc",
            nodeSelectedRing: "#38bdf8",
            linkStroke: "rgba(71, 85, 105, 0.35)",
            linkStrokeDim: "rgba(71, 85, 105, 0.05)"
        };

        this.links.forEach(l => {
            const isTrace = isTracePathEdge(l.source.id, l.target.id);
            const isHovered = this.hoverNode && (l.source === this.hoverNode || l.target === this.hoverNode);
            const srcFocus = focused ? focused.get(l.source.id) : null;
            const tgtFocus = focused ? focused.get(l.target.id) : null;
            const isConnectedToFocus = !!(srcFocus && tgtFocus);

            let strokeColor = themeColors.linkStroke;
            let lineWidth = 1.0;

            if (isTrace) {
                strokeColor = themeColors.nodeSelectedRing || "#38bdf8";
                lineWidth = 3.0;
            } else if (isHovered) {
                strokeColor = themeColors.nodeSelectedRing || "#38bdf8";
                lineWidth = 2.2;
            } else if (isConnectedToFocus) {
                const minDepth = Math.min(srcFocus.depth, tgtFocus.depth);
                lineWidth = minDepth === 0 ? 2.2 : 1.4;
                strokeColor = (srcFocus.direction === "upstream" || tgtFocus.direction === "upstream") ? (themeColors.nodeTextExternalFile || "#c084fc") : (themeColors.nodeSelectedRing || "#38bdf8");
            } else if (focused) {
                strokeColor = themeColors.linkStrokeDim;
            }

            this.ctx.strokeStyle = strokeColor;
            this.ctx.lineWidth = lineWidth;
            this.ctx.beginPath();
            this.ctx.moveTo(l.source.x, l.source.y);
            this.ctx.lineTo(l.target.x, l.target.y);
            this.ctx.stroke();

            const dx = l.target.x - l.source.x;
            const dy = l.target.y - l.source.y;
            const angle = Math.atan2(dy, dx);
            const headlen = 5;
            const targetX = l.target.x - Math.cos(angle) * (l.target.radius + 2);
            const targetY = l.target.y - Math.sin(angle) * (l.target.radius + 2);

            this.ctx.fillStyle = strokeColor;
            this.ctx.beginPath();
            this.ctx.moveTo(targetX, targetY);
            this.ctx.lineTo(targetX - headlen * Math.cos(angle - Math.PI / 6), targetY - headlen * Math.sin(angle - Math.PI / 6));
            this.ctx.lineTo(targetX - headlen * Math.cos(angle + Math.PI / 6), targetY - headlen * Math.sin(angle + Math.PI / 6));
            this.ctx.fill();

            if (isTrace) {
                const t = (Math.sin(this.pulsePhase) + 1) / 2;
                const px = l.source.x + (l.target.x - l.source.x) * t;
                const py = l.source.y + (l.target.y - l.source.y) * t;
                this.ctx.beginPath();
                this.ctx.arc(px, py, 3.5, 0, Math.PI * 2);
                this.ctx.fillStyle = "#ffffff";
                this.ctx.shadowColor = themeColors.nodeSelectedRing || "#38bdf8";
                this.ctx.shadowBlur = 8;
                this.ctx.fill();
                this.ctx.shadowBlur = 0;
            }
        });

        this.nodes.forEach(n => {
            const isSelected = selNodeId && n.id === selNodeId;
            const isHovered = this.hoverNode === n;
            const isUnused = unusedNodeIds && unusedNodeIds.has(n.id);
            const focusInfo = focused ? focused.get(n.id) : null;
            const isInFocus = !focused || !!focusInfo;
            const isTraced = tracePath.includes(n.id);

            let nodeColor;
            if (appState.colorMode === "feature") {
                nodeColor = appState.getFeatureColor(n.feature);
            } else {
                nodeColor = appState.LAYER_COLORS[n.layer] || "#0284c7";
            }

            if (isUnused && !isSelected && !isTraced) {
                nodeColor = "#64748b";
            }

            this.ctx.save();
            if (!isInFocus) {
                this.ctx.globalAlpha = 0.08;
            } else if (focused && focusInfo) {
                if (focusInfo.depth === 0) {
                    this.ctx.globalAlpha = 1.0;
                } else {
                    this.ctx.globalAlpha = Math.max(0.35, 1.0 - (focusInfo.depth - 1) * 0.15);
                }
            } else {
                this.ctx.globalAlpha = 1.0;
            }

            this.drawNodePath(n, 0);
            this.ctx.fillStyle = nodeColor;
            this.ctx.fill();

            if (n.isExternal) {
                this.ctx.save();
                this.ctx.setLineDash([3, 2]);
                this.drawNodePath(n, 3.5);
                this.ctx.strokeStyle = themeColors.nodeTextExternalFile || "#c084fc";
                this.ctx.lineWidth = 1.6;
                this.ctx.stroke();
                this.ctx.restore();
            }

            if (isTraced) {
                this.drawNodePath(n, 5);
                this.ctx.strokeStyle = themeColors.nodeSelectedRing || "#38bdf8";
                this.ctx.lineWidth = 3;
                this.ctx.stroke();
            } else if (isSelected) {
                this.drawNodePath(n, 4);
                this.ctx.strokeStyle = themeColors.nodeSelectedRing || "#38bdf8";
                this.ctx.lineWidth = 2.5;
                this.ctx.stroke();
            } else if (isHovered) {
                this.drawNodePath(n, 2.5);
                this.ctx.strokeStyle = themeColors.nodeHoverRing || "#f8fafc";
                this.ctx.lineWidth = 1.5;
                this.ctx.stroke();
            }

            if (this.transform.k > 0.45 || isHovered || isSelected || isTraced || isInFocus) {
                this.ctx.font = isSelected || isTraced ? "bold 11px sans-serif" : "10px sans-serif";
                const textColor = isUnused
                    ? themeColors.nodeTextDim
                    : (isSelected || isTraced
                        ? themeColors.nodeSelectedRing
                        : (n.isExternal ? themeColors.nodeTextExternal : themeColors.nodeText));
                this.ctx.fillStyle = textColor;
                this.ctx.textAlign = "center";
                this.ctx.fillText(n.label, n.x, n.y + n.radius + 12);

                if (n.isExternal && n.fileId && (this.transform.k > 0.4 || isHovered || isSelected || isInFocus)) {
                    const extFile = n.fileId.split("/").pop();
                    this.ctx.font = "8px sans-serif";
                    this.ctx.fillStyle = themeColors.nodeTextExternalFile || "#c084fc";
                    this.ctx.fillText(`[${extFile}]`, n.x, n.y + n.radius + 22);
                }
            }

            this.ctx.restore();
        });

        this.ctx.restore();
    }

    renderClusterHulls() {
        const clusters = new Map();
        const isSymbolsMode = this.isMain && appState.graphMode === "symbols";

        this.nodes.forEach(n => {
            const clusterKey = isSymbolsMode ? (n.fileId || n.folder || "root") : (n.feature || "root");
            if (!clusters.has(clusterKey)) clusters.set(clusterKey, []);
            clusters.get(clusterKey).push(n);
        });

        clusters.forEach((nodes, key) => {
            if (nodes.length < (isSymbolsMode ? 1 : 2)) return;
            let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
            nodes.forEach(n => {
                if (n.x < minX) minX = n.x;
                if (n.x > maxX) maxX = n.x;
                if (n.y < minY) minY = n.y;
                if (n.y > maxY) maxY = n.y;
            });

            const pad = isSymbolsMode ? 18 : 24;
            const sampleNode = nodes[0];
            const color = isSymbolsMode
                ? (sampleNode.layer ? (appState.LAYER_COLORS[sampleNode.layer] || "#38bdf8") : "#38bdf8")
                : appState.getFeatureColor(key);
            const label = isSymbolsMode ? key.split("/").pop() : key;

            this.ctx.save();
            this.ctx.fillStyle = color;
            this.ctx.globalAlpha = 0.05;
            this.ctx.strokeStyle = color;
            this.ctx.lineWidth = 1;
            this.ctx.beginPath();
            this.ctx.roundRect(minX - pad, minY - pad, maxX - minX + pad * 2, maxY - minY + pad * 2, 10);
            this.ctx.fill();
            this.ctx.globalAlpha = 0.22;
            this.ctx.stroke();

            this.ctx.globalAlpha = 0.7;
            this.ctx.font = "bold 9px sans-serif";
            this.ctx.fillStyle = color;
            this.ctx.textAlign = "left";
            this.ctx.fillText(label, minX - pad + 8, minY - pad + 14);
            this.ctx.restore();
        });
    }

    zoomIn() {
        this.zoomBy(1.3);
    }

    zoomOut() {
        this.zoomBy(0.75);
    }

    zoomBy(factor) {
        const w = this.canvas.width / window.devicePixelRatio;
        const h = this.canvas.height / window.devicePixelRatio;
        const cx = w / 2;
        const cy = h / 2;
        const newK = Math.max(0.05, Math.min(10, this.transform.k * factor));

        this.transform.x = cx - (cx - this.transform.x) * (newK / this.transform.k);
        this.transform.y = cy - (cy - this.transform.y) * (newK / this.transform.k);
        this.transform.k = newK;
        if (this.miniMap) this.miniMap.update();
    }

    panTo(worldX, worldY) {
        const w = this.canvas.width / window.devicePixelRatio;
        const h = this.canvas.height / window.devicePixelRatio;
        this.transform.x = w / 2 - worldX * this.transform.k;
        this.transform.y = h / 2 - worldY * this.transform.k;
        if (this.miniMap) this.miniMap.update();
    }

    resetView() {
        this.fitToScreen();
    }

    fitToScreen() {
        if (!this.canvas) return;
        const validNodes = (this.nodes || []).filter(n => isFinite(n.x) && isFinite(n.y));
        if (validNodes.length === 0) {
            this.transform = { x: 0, y: 0, k: 1 };
            if (this.miniMap) this.miniMap.update();
            return;
        }
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        validNodes.forEach(n => {
            if (n.x < minX) minX = n.x;
            if (n.x > maxX) maxX = n.x;
            if (n.y < minY) minY = n.y;
            if (n.y > maxY) maxY = n.y;
        });

        if (minX === Infinity || !isFinite(minX)) {
            minX = -100; maxX = 100; minY = -100; maxY = 100;
        }

        const pad = 60;
        const spanX = Math.max(100, maxX - minX + pad * 2);
        const spanY = Math.max(100, maxY - minY + pad * 2);

        const w = (this.canvas.width / window.devicePixelRatio) || this.canvas.clientWidth || window.innerWidth;
        const h = (this.canvas.height / window.devicePixelRatio) || this.canvas.clientHeight || window.innerHeight;

        const k = Math.min(w / spanX, h / spanY, 1.8);
        const midX = (minX + maxX) / 2;
        const midY = (minY + maxY) / 2;

        const minK = !this.isMain ? 0.45 : 0.15;
        this.transform.k = Math.max(minK, Math.min(1.8, isFinite(k) ? k : 1));
        this.transform.x = w / 2 - midX * this.transform.k;
        this.transform.y = h / 2 - midY * this.transform.k;
        if (this.miniMap) this.miniMap.update();
    }
}

window.GraphCanvas = GraphCanvas;
