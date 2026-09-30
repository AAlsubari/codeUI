/**
 * Application State container for CodeUI interactive explorer.
 */
class AppState {
    constructor() {
        this.rawGraph = { files: [], symbols: [], edges: [], files_info: {} };
        this.defectsData = [];
        this.graphMode = "files"; // "files" | "symbols"
        this.layoutMode = "force"; // "force" | "hierarchical" | "radial" | "clusters"
        this.colorMode = "layer"; // "layer" | "feature"
        this.theme = "dark";
        this.searchQuery = "";
        this.activeLayerFilter = "all";
        this.selectedFileNodeId = null;
        this.focusedNeighborhood = null;

        // Path tracer state
        this.tracerActive = false;
        this.traceStartNode = null;
        this.traceEndNode = null;
        this.activeTracePath = [];
        this.currentTraceHopIdx = 0;

        // Visual toggles
        this.unusedHighlightMode = false;
        this.directDiskWrite = false;
        this.hudExplicitlyClosed = false;
        this.clusterHullsMode = true;

        // Symbol filter toggles for symbols view (dynamically populated from AST symbols)
        this.symbolKindFilters = {};

        // SubGraph window management
        this.activeSubgraphs = new Map();
        this.nextWindowOffset = 20;

        // Color maps
        this.LAYER_COLORS = {
            entry: "#a855f7",
            frontend: "#3b82f6",
            backend: "#22c55e",
            shared: "#06b6d4",
            test: "#eab308",
            tests: "#eab308",
            external: "#64748b",
            other: "#64748b"
        };
    }

    getFeatureColor(feature) {
        if (!feature || feature === "root" || feature === "external") return "#64748b";
        const palette = [
            "#ec4899", "#8b5cf6", "#3b82f6", "#06b6d4", 
            "#10b981", "#f59e0b", "#ef4444", "#a855f7"
        ];
        let hash = 0;
        for (let i = 0; i < feature.length; i++) {
            hash = (hash << 5) - hash + feature.charCodeAt(i);
        }
        return palette[Math.abs(hash) % palette.length];
    }

    getUnusedNodeIds() {
        if (!this.rawGraph) return new Set();
        const nodes = this.graphMode === "files" ? (this.rawGraph.files || []) : (this.rawGraph.symbols || []);
        const edges = this.rawGraph.edges || [];
        const targetIds = new Set(edges.map(e => e.target_id));
        const unused = new Set();

        nodes.forEach(n => {
            const id = typeof n === "string" ? n : n.id;
            if (!targetIds.has(id)) {
                const layer = (this.rawGraph.files_info && this.rawGraph.files_info[id]?.layer) || (typeof n === "object" ? n.layer : "");
                if (layer !== "entry" && layer !== "test" && layer !== "tests") {
                    unused.add(id);
                }
            }
        });
        return unused;
    }
}

window.appState = new AppState();
