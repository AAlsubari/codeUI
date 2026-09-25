"""Registry mapping file paths to appropriate language analyzers."""
from pathlib import Path
from typing import Dict, List, Optional, Type
from codeui.lang.base import LanguageAnalyzer
from codeui.lang.python import PythonLanguageAnalyzer
from codeui.lang.ts import TSLanguageAnalyzer
from codeui.lang.go import GoLanguageAnalyzer
from codeui.lang.rust import RustLanguageAnalyzer
from codeui.lang.generic import GenericLanguageAnalyzer

class LanguageRegistry:
    """Registry maintaining active language adapters.
    Example:
        >>> reg = LanguageRegistry()
        >>> analyzer = reg.get_analyzer(Path("app.py"))
        >>> analyzer.language
        'python'
    """
    def __init__(self) -> None:
        self._analyzers: List[LanguageAnalyzer] = [
            PythonLanguageAnalyzer(),
            TSLanguageAnalyzer(),
            GoLanguageAnalyzer(),
            RustLanguageAnalyzer(),
            GenericLanguageAnalyzer(),
        ]
        self._ext_map: Dict[str, LanguageAnalyzer] = {}
        for analyzer in self._analyzers:
            for ext in analyzer.extensions:
                self._ext_map[ext.lower()] = analyzer

    def register(self, analyzer: LanguageAnalyzer) -> None:
        """Register a custom language analyzer.
        Example:
            >>> reg = LanguageRegistry()
            >>> reg.register(GenericLanguageAnalyzer())
        """
        self._analyzers.append(analyzer)
        for ext in analyzer.extensions:
            self._ext_map[ext.lower()] = analyzer

    def get_analyzer(self, path: Path) -> LanguageAnalyzer:
        """Find language analyzer matching file extension or filename.
        Example:
            >>> reg = LanguageRegistry()
            >>> reg.get_analyzer(Path("main.ts")).language
            'typescript'
        """
        ext = path.suffix.lower()
        if not ext and path.name:
            ext = path.name.lower()
        return self._ext_map.get(ext, self._analyzers[-1])

    def supported_languages(self) -> List[str]:
        """List registered supported languages.
        Example:
            >>> reg = LanguageRegistry()
            >>> 'python' in reg.supported_languages()
            True
        """
        return sorted(list(set(a.language for a in self._analyzers)))

    def get_supported_extensions(self) -> set[str]:
        """Return file extensions supported by first-class AST language analyzers.
        Example:
            >>> reg = LanguageRegistry()
            >>> '.py' in reg.get_supported_extensions()
            True
        """
        exts: set[str] = set()
        for a in self._analyzers:
            if getattr(a, "has_ast_support", True) and getattr(a, "is_supported", True) and a.language != "generic":
                exts.update(a.extensions)
        return exts

    def get_all_extensions(self) -> set[str]:
        """Return all registered file extensions including fallback analyzers.
        Example:
            >>> reg = LanguageRegistry()
            >>> '.py' in reg.get_all_extensions()
            True
        """
        return set(self._ext_map.keys())
