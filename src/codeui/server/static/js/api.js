/**
 * REST API client wrapper for codeui server endpoints.
 */
const CSRF_TOKEN = "codeui-local-csrf-token";

class CodeUIAPI {
    static async getGraph(forceRefresh = false) {
        const url = forceRefresh ? "/api/v1/graph?refresh=1" : "/api/v1/graph";
        const res = await fetch(url);
        if (!res.ok) {
            let errMsg = `Server returned status ${res.status}`;
            try {
                const data = await res.json();
                if (data && data.error) errMsg = data.error;
            } catch (_) {}
            throw new Error(errMsg);
        }
        const text = await res.text();
        try {
            return JSON.parse(text);
        } catch (_) {
            throw new Error("Invalid graph response received from server");
        }
    }

    static async cloneRepo(repo) {
        const res = await fetch("/api/v1/clone", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": CSRF_TOKEN
            },
            body: JSON.stringify({ repo })
        });
        if (!res.ok) {
            let errMsg = `Server returned status ${res.status}`;
            try {
                const data = await res.json();
                if (data && data.error) errMsg = data.error;
            } catch (_) {}
            throw new Error(errMsg);
        }
        return await res.json();
    }

    static async refreshProject() {
        const res = await fetch("/api/v1/refresh", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": CSRF_TOKEN
            },
            body: JSON.stringify({})
        });
        if (!res.ok) {
            let errMsg = `Server returned status ${res.status}`;
            try {
                const data = await res.json();
                if (data && data.error) errMsg = data.error;
            } catch (_) {}
            throw new Error(errMsg);
        }
        const text = await res.text();
        try {
            return JSON.parse(text);
        } catch (_) {
            throw new Error("Invalid refresh response received from server");
        }
    }

    static async getSubGraph(filePath, symbolId = "") {
        let url = `/api/v1/subgraph?file=${encodeURIComponent(filePath)}`;
        if (symbolId) url += `&symbol_id=${encodeURIComponent(symbolId)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Failed to fetch subgraph for ${filePath}`);
        return await res.json();
    }

    static async getDefects() {
        const res = await fetch("/api/v1/defects");
        if (!res.ok) throw new Error("Failed to fetch defect findings");
        return await res.json();
    }

    static async getFile(filePath) {
        const res = await fetch(`/api/v1/file?path=${encodeURIComponent(filePath)}`);
        if (!res.ok) throw new Error(`Failed to fetch file ${filePath}`);
        return await res.json();
    }

    static async applyEdit(targetId, newValue, kind = "replace_file", directDisk = true) {
        const res = await fetch("/api/v1/edit", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": CSRF_TOKEN
            },
            body: JSON.stringify({ kind, target_id: targetId, new_value: newValue, direct_disk: directDisk })
        });
        if (!res.ok) throw new Error(`Failed to apply edit for ${targetId}`);
        return await res.json();
    }

    static async revertEdit(targetId) {
        const res = await fetch("/api/v1/revert", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": CSRF_TOKEN
            },
            body: JSON.stringify({ target_id: targetId })
        });
        if (!res.ok) throw new Error(`Failed to revert ${targetId}`);
        return await res.json();
    }

    static exportZip() {
        window.location.href = "/__export_zip__";
    }
}

window.CodeUIAPI = CodeUIAPI;
