const THEMES = {
    dark: {
        id: "dark",
        name: "Dark Slate",
        cssVars: {
            "--bg-base": "#0f172a",
            "--bg-surface": "#1e293b",
            "--bg-elevated": "#334155",
            "--border-subtle": "#334155",
            "--border-strong": "#475569",
            "--text-main": "#f8fafc",
            "--text-muted": "#94a3b8",
            "--text-dim": "#64748b",
            "--primary": "#2563eb",
            "--primary-hover": "#1d4ed8",
            "--accent": "#38bdf8",
            "--danger": "#ef4444",
            "--warning": "#f59e0b",
            "--success": "#10b981",
            "--purple": "#a855f7",
            "--pink": "#ec4899",
            "--panel-overlay-bg": "rgba(15, 23, 42, 0.88)",
            "--panel-header-bg": "#1e293b",
            "--minimap-bg": "rgba(15, 23, 42, 0.40)",
            "--editor-bg": "#070a12",
            "--editor-text": "#f8fafc",
            "--editor-line-bg": "#0b0f19",
            "--editor-line-text": "#475569",
            "--subgraph-bg": "rgba(19, 27, 46, 0.98)",
            "--subgraph-bar-bg": "rgba(15, 23, 42, 0.94)",
            "--subgraph-bar-text": "#cbd5e1",
            "--chip-bg": "rgba(30, 41, 59, 0.8)",
            "--chip-text": "#cbd5e1",
            "--card-hover-bg": "#1e293b"
        },
        canvas: {
            nodeText: "#f1f5f9",
            nodeTextDim: "#94a3b8",
            nodeTextExternal: "#e9d5ff",
            nodeTextExternalFile: "#c084fc",
            nodeHoverRing: "#f8fafc",
            nodeSelectedRing: "#38bdf8",
            linkStroke: "rgba(71, 85, 105, 0.35)",
            linkStrokeDim: "rgba(71, 85, 105, 0.05)",
            minimapDots: "rgba(51, 65, 85, 0.35)",
            minimapLinks: "rgba(71, 85, 105, 0.35)",
            minimapViewfinder: "rgba(56, 189, 248, 0.15)",
            minimapViewfinderBorder: "#38bdf8"
        }
    },
    cyber: {
        id: "cyber",
        name: "Cyber Matrix",
        cssVars: {
            "--bg-base": "#030712",
            "--bg-surface": "#0b132b",
            "--bg-elevated": "#1c2541",
            "--border-subtle": "#1f293d",
            "--border-strong": "#00f0ff",
            "--text-main": "#f0fdfa",
            "--text-muted": "#5eead4",
            "--text-dim": "#2dd4bf",
            "--primary": "#00f0ff",
            "--primary-hover": "#38bdf8",
            "--accent": "#00f0ff",
            "--danger": "#ef4444",
            "--warning": "#f59e0b",
            "--success": "#10b981",
            "--purple": "#a855f7",
            "--pink": "#ec4899",
            "--panel-overlay-bg": "rgba(3, 7, 18, 0.90)",
            "--panel-header-bg": "#0b132b",
            "--minimap-bg": "rgba(3, 7, 18, 0.40)",
            "--editor-bg": "#020617",
            "--editor-text": "#f0fdfa",
            "--editor-line-bg": "#090e1a",
            "--editor-line-text": "#2dd4bf",
            "--subgraph-bg": "rgba(11, 19, 43, 0.98)",
            "--subgraph-bar-bg": "rgba(11, 19, 43, 0.94)",
            "--subgraph-bar-text": "#5eead4",
            "--chip-bg": "rgba(28, 37, 65, 0.8)",
            "--chip-text": "#5eead4",
            "--card-hover-bg": "#1c2541"
        },
        canvas: {
            nodeText: "#f0fdfa",
            nodeTextDim: "#2dd4bf",
            nodeTextExternal: "#a5f3fc",
            nodeTextExternalFile: "#00f0ff",
            nodeHoverRing: "#00f0ff",
            nodeSelectedRing: "#00f0ff",
            linkStroke: "rgba(0, 240, 255, 0.35)",
            linkStrokeDim: "rgba(0, 240, 255, 0.05)",
            minimapDots: "rgba(0, 240, 255, 0.25)",
            minimapLinks: "rgba(0, 240, 255, 0.35)",
            minimapViewfinder: "rgba(0, 240, 255, 0.18)",
            minimapViewfinderBorder: "#00f0ff"
        }
    },
    light: {
        id: "light",
        name: "Light Studio",
        cssVars: {
            "--bg-base": "#f8fafc",
            "--bg-surface": "#ffffff",
            "--bg-elevated": "#f1f5f9",
            "--border-subtle": "#e2e8f0",
            "--border-strong": "#cbd5e1",
            "--text-main": "#0f172a",
            "--text-muted": "#475569",
            "--text-dim": "#64748b",
            "--primary": "#2563eb",
            "--primary-hover": "#1d4ed8",
            "--accent": "#0284c7",
            "--danger": "#dc2626",
            "--warning": "#d97706",
            "--success": "#059669",
            "--purple": "#9333ea",
            "--pink": "#db2777",
            "--panel-overlay-bg": "rgba(255, 255, 255, 0.92)",
            "--panel-header-bg": "#ffffff",
            "--minimap-bg": "rgba(255, 255, 255, 0.55)",
            "--editor-bg": "#ffffff",
            "--editor-text": "#0f172a",
            "--editor-line-bg": "#f8fafc",
            "--editor-line-text": "#64748b",
            "--subgraph-bg": "rgba(255, 255, 255, 0.98)",
            "--subgraph-bar-bg": "rgba(241, 245, 249, 0.94)",
            "--subgraph-bar-text": "#0f172a",
            "--chip-bg": "rgba(226, 232, 240, 0.8)",
            "--chip-text": "#0f172a",
            "--card-hover-bg": "#f1f5f9"
        },
        canvas: {
            nodeText: "#0f172a",
            nodeTextDim: "#64748b",
            nodeTextExternal: "#7e22ce",
            nodeTextExternalFile: "#6b21a8",
            nodeHoverRing: "#0f172a",
            nodeSelectedRing: "#0284c7",
            linkStroke: "rgba(100, 116, 139, 0.45)",
            linkStrokeDim: "rgba(148, 163, 184, 0.12)",
            minimapDots: "rgba(148, 163, 184, 0.45)",
            minimapLinks: "rgba(100, 116, 139, 0.40)",
            minimapViewfinder: "rgba(2, 132, 199, 0.15)",
            minimapViewfinderBorder: "#0284c7"
        }
    },
    forest: {
        id: "forest",
        name: "Forest Matrix",
        cssVars: {
            "--bg-base": "#061a14",
            "--bg-surface": "#0d2820",
            "--bg-elevated": "#173d32",
            "--border-subtle": "#173d32",
            "--border-strong": "#10b981",
            "--text-main": "#ecfdf5",
            "--text-muted": "#6ee7b7",
            "--text-dim": "#34d399",
            "--primary": "#059669",
            "--primary-hover": "#047857",
            "--accent": "#10b981",
            "--danger": "#ef4444",
            "--warning": "#f59e0b",
            "--success": "#10b981",
            "--purple": "#a855f7",
            "--pink": "#ec4899",
            "--panel-overlay-bg": "rgba(6, 26, 20, 0.90)",
            "--panel-header-bg": "#0d2820",
            "--minimap-bg": "rgba(6, 26, 20, 0.45)",
            "--editor-bg": "#03110d",
            "--editor-text": "#ecfdf5",
            "--editor-line-bg": "#061a14",
            "--editor-line-text": "#34d399",
            "--subgraph-bg": "rgba(13, 40, 32, 0.98)",
            "--subgraph-bar-bg": "rgba(13, 40, 32, 0.94)",
            "--subgraph-bar-text": "#6ee7b7",
            "--chip-bg": "rgba(23, 61, 50, 0.8)",
            "--chip-text": "#6ee7b7",
            "--card-hover-bg": "#173d32"
        },
        canvas: {
            nodeText: "#ecfdf5",
            nodeTextDim: "#34d399",
            nodeTextExternal: "#a7f3d0",
            nodeTextExternalFile: "#10b981",
            nodeHoverRing: "#10b981",
            nodeSelectedRing: "#10b981",
            linkStroke: "rgba(16, 185, 129, 0.35)",
            linkStrokeDim: "rgba(16, 185, 129, 0.06)",
            minimapDots: "rgba(16, 185, 129, 0.30)",
            minimapLinks: "rgba(16, 185, 129, 0.35)",
            minimapViewfinder: "rgba(16, 185, 129, 0.20)",
            minimapViewfinderBorder: "#10b981"
        }
    },
    monokai: {
        id: "monokai",
        name: "Monokai Pro",
        cssVars: {
            "--bg-base": "#272822",
            "--bg-surface": "#383830",
            "--bg-elevated": "#49483e",
            "--border-subtle": "#49483e",
            "--border-strong": "#f92672",
            "--text-main": "#f8f8f2",
            "--text-muted": "#a6e22e",
            "--text-dim": "#75715e",
            "--primary": "#f92672",
            "--primary-hover": "#fd5c63",
            "--accent": "#66d9ef",
            "--danger": "#f92672",
            "--warning": "#fd971f",
            "--success": "#a6e22e",
            "--purple": "#ae81ff",
            "--pink": "#f92672",
            "--panel-overlay-bg": "rgba(39, 40, 34, 0.90)",
            "--panel-header-bg": "#383830",
            "--minimap-bg": "rgba(39, 40, 34, 0.45)",
            "--editor-bg": "#1e1f1c",
            "--editor-text": "#f8f8f2",
            "--editor-line-bg": "#272822",
            "--editor-line-text": "#75715e",
            "--subgraph-bg": "rgba(56, 56, 48, 0.98)",
            "--subgraph-bar-bg": "rgba(56, 56, 48, 0.94)",
            "--subgraph-bar-text": "#a6e22e",
            "--chip-bg": "rgba(73, 72, 62, 0.8)",
            "--chip-text": "#a6e22e",
            "--card-hover-bg": "#49483e"
        },
        canvas: {
            nodeText: "#f8f8f2",
            nodeTextDim: "#75715e",
            nodeTextExternal: "#ae81ff",
            nodeTextExternalFile: "#66d9ef",
            nodeHoverRing: "#66d9ef",
            nodeSelectedRing: "#f92672",
            linkStroke: "rgba(102, 217, 239, 0.35)",
            linkStrokeDim: "rgba(102, 217, 239, 0.06)",
            minimapDots: "rgba(117, 113, 94, 0.35)",
            minimapLinks: "rgba(102, 217, 239, 0.35)",
            minimapViewfinder: "rgba(249, 38, 114, 0.20)",
            minimapViewfinderBorder: "#f92672"
        }
    }
};

class ThemeManager {
    static themes = THEMES;

    static getThemes() {
        return Object.values(this.themes);
    }

    static getTheme(themeId) {
        return this.themes[themeId] || this.themes.dark;
    }

    static getCanvasColors(themeId) {
        const id = themeId || (window.appState ? window.appState.theme : "dark");
        const theme = this.getTheme(id);
        return theme.canvas;
    }

    static registerTheme(themeConfig) {
        if (!themeConfig || !themeConfig.id) return;
        this.themes[themeConfig.id] = themeConfig;
        this.populateThemeSelector();
    }

    static populateThemeSelector() {
        const select = document.getElementById("select-theme");
        if (!select) return;
        const current = window.appState ? window.appState.theme : "dark";
        select.innerHTML = Object.values(this.themes).map(t =>
            `<option value="${t.id}" ${t.id === current ? "selected" : ""}>Theme: ${t.name}</option>`
        ).join("");
    }

    static applyTheme(themeId) {
        const theme = this.getTheme(themeId);
        if (window.appState) {
            window.appState.theme = theme.id;
        }
        document.body.setAttribute("data-theme", theme.id);

        if (theme.cssVars) {
            for (const [key, val] of Object.entries(theme.cssVars)) {
                document.documentElement.style.setProperty(key, val);
            }
        }

        const select = document.getElementById("select-theme");
        if (select && select.value !== theme.id) {
            select.value = theme.id;
        }

        try {
            localStorage.setItem("codeui_theme", theme.id);
        } catch (_) {}

        if (window.mainCanvas) {
            window.mainCanvas.render();
            if (window.mainCanvas.miniMap) {
                window.mainCanvas.miniMap.update();
            }
        }

        if (window.appState && window.appState.activeSubgraphs) {
            window.appState.activeSubgraphs.forEach(win => {
                if (win.canvasInstance) {
                    win.canvasInstance.render();
                }
            });
        }
    }

    static init() {
        this.populateThemeSelector();
        let initialTheme = "dark";
        try {
            const saved = localStorage.getItem("codeui_theme");
            if (saved && this.themes[saved]) {
                initialTheme = saved;
            }
        } catch (_) {}
        this.applyTheme(initialTheme);
    }
}

window.ThemeManager = ThemeManager;
