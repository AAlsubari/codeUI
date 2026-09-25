"""Plugin entry-point registry for third-party adapters and analyzers."""
import importlib.metadata
from typing import Any, List

class PluginRegistry:
    """Manages discovery and loading of entrypoint-based codeui plugins.
    Example:
        >>> reg = PluginRegistry()
        >>> isinstance(reg.load_plugins(), list)
        True
    """
    def load_plugins(self) -> List[Any]:
        """Load external plugins registered under 'codeui.plugins' entrypoint group.
        Example:
            >>> reg = PluginRegistry()
            >>> plugins = reg.load_plugins()
            >>> isinstance(plugins, list)
            True
        """
        loaded = []
        try:
            entry_points = importlib.metadata.entry_points()
            if hasattr(entry_points, "select"):
                eps = entry_points.select(group="codeui.plugins")
            else:
                eps = entry_points.get("codeui.plugins", [])
            for ep in eps:
                loaded.append(ep.load())
        except Exception:
            pass
        return loaded
