/**
 * Global reactive state container for codeui visualizer.
 */
class State {
    constructor() {
        this.rawGraph = { files: [], files_info: {}, symbols: [], edges: [], findings: [] };
        this.defectsData = [];
        this.graphMode = "files"; // "files" | "symbols"
        this.colorMode = "layer"; // "layer" | "feature"
        this.layoutMode = "force"; // "force" | "hierarchical" | "radial" | "clusters"
        this.theme = "dark"; // "dark" | "cyber" | "light"
        this.activeLayerFilter = "all";
        this.searchQuery = "";
        this.selectedFileNodeId = null;
        this.unusedHighlightMode = false;
        this.clusterHullsMode = true;
        this.directDiskWrite = true;

        // Path Tracer State
        this.tracerActive = false;
        this.traceStartNode = null;
        this.traceEndNode = null;
        this.activeTracePath = [];
        this.tracerStepIndex = 0;

        // Focus / Multi-Hop Transitive Neighborhood Isolation
        this.focusedNeighborhood = null; // Map<nodeId, { depth: number, direction: 'upstream' | 'downstream' | 'root' }>

        // Active Edge Filters
        this.activeEdgeFilters = new Set(["imports", "calls", "inherits", "contains", "uses", "all"]);

        // Ignored defect findings sets
        this.ignoredDefectIds = new Set();
        this.ignoredRuleIds = new Set();

        // Multi SubGraph Window State Store
        this.activeSubgraphs = new Map();
        this.nextWindowOffset = 30;

        // Colors Mapping
        this.LAYER_COLORS = {
            entry: "#a855f7",
            frontend: "#3b82f6",
            backend: "#22c55e",
            shared: "#06b6d4",
            test: "#eab308",
            config: "#64748b",
            other: "#0284c7"
        };
    }

    getFeatureColor(feature) {
        if (!feature || feature === "root") return "#38bdf8";
        let hash = 0;
        for (let i = 0; i < feature.length; i++) {
            hash = feature.charCodeAt(i) + ((hash << 5) - hash);
        }
        const h = Math.abs(hash) % 360;
        return `hsl(${h}, 75%, 60%)`;
    }

    getUnusedNodeIds() {
        const unused = new Set();
        if (!this.rawGraph) return unused;

        const unusedRuleFindings = (this.defectsData || []).filter(d => {
            const rid = (d.rule_id || "").toLowerCase();
            return rid.includes("unused") || rid.includes("dead") || rid.includes("unreachable");
        });

        unusedRuleFindings.forEach(d => {
            if (d.location && d.location.file_id) {
                if (this.graphMode === "files") {
                    unused.add(d.location.file_id);
                } else if (d.symbol_id) {
                    unused.add(d.symbol_id);
                }
            }
        });

        const referencedTargets = new Set();
        (this.rawGraph.edges || []).forEach(e => {
            if (e.kind === "contains") return;
            if (e.target_id) referencedTargets.add(e.target_id);
        });

        const normSymId = (id) => {
            if (!id) return "";
            return id.replace(/\\/g, "/").replace(/\.(ts|tsx|py|js|jsx|go|rs|cpp|h|java)\b/i, "");
        };

        if (this.graphMode === "symbols") {
            const entryNames = ["main", "index", "App", "app", "run", "handler", "constructor", "init", "start", "__init__"];
            (this.rawGraph.symbols || []).forEach(s => {
                if (s.kind === "file") return;
                if (entryNames.includes(s.name) || (typeof s.name === "string" && s.name.startsWith("test_"))) return;
                const sIdNorm = normSymId(s.id);
                const sQualNorm = normSymId(s.qualified_name);
                const sNameSuff = "::" + s.name;
                let isReferenced = false;
                for (let ref of referencedTargets) {
                    const refNorm = normSymId(ref);
                    if (refNorm === sIdNorm || refNorm === sQualNorm || ref.endsWith(sNameSuff)) {
                        isReferenced = true;
                        break;
                    }
                }
                if (!isReferenced) {
                    unused.add(s.id);
                }
            });
        } else {
            const allFiles = this.rawGraph.files || [];
            const filesInfo = this.rawGraph.files_info || {};
            allFiles.forEach(f => {
                const info = filesInfo[f] || {};
                const parts = f.split("/");
                const filename = parts[parts.length - 1].toLowerCase();
                const stem = filename.split(".")[0];
                if (info.layer === "entry" || info.layer === "test" || info.layer === "config" ||
                    ["main", "index", "app", "server", "cli", "setup", "__init__", "conftest"].includes(stem) ||
                    filename.startsWith(".")) return;
                let isReferenced = false;
                for (let e of (this.rawGraph.edges || [])) {
                    if (e.kind === "contains") continue;
                    const srcFile = e.source_id.split("::")[0];
                    if (srcFile === f) continue;
                    let tgt = e.target_id;
                    if (tgt.startsWith("module::")) {
                        tgt = tgt.replace("module::", "").replace(/\./g, "/");
                    }
                    const tgtFile = tgt.split("::")[0];
                    const normF = f.replace(/\\/g, "/");
                    const normTgt = tgtFile.replace(/\\/g, "/");
                    const stemF = normF.split(".")[0];
                    const stemTgt = normTgt.split(".")[0];
                    if (normF === normTgt || stemF === stemTgt || normF.endsWith("/" + normTgt) || stemF.endsWith("/" + stemTgt) || normF.includes(normTgt) || (normTgt.length > 3 && normF.endsWith(normTgt))) {
                        isReferenced = true;
                        break;
                    }
                }
                if (!isReferenced) {
                    unused.add(f);
                }
            });
        }
        return unused;
    }
}

window.appState = new State();
