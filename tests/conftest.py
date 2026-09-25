"""Pytest shared test fixtures."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from codeui.core.graph import Graph
from codeui.core.ir import Location, Symbol, SymbolKind, Visibility
from codeui.core.override import OverrideStore

@pytest.fixture
def temp_project_dir():
    """Create a temporary directory simulating a codebase."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("def main():\n    print('Hello')\n", encoding="utf-8")
        (root / "src" / "utils.py").write_text("def helper():\n    pass\n", encoding="utf-8")
        yield root

@pytest.fixture
def sample_graph():
    """Build a standard in-memory Graph for tests."""
    g = Graph()
    s1 = Symbol(
        id="app.py::main",
        name="main",
        qualified_name="app.main",
        kind=SymbolKind.FUNCTION,
        language="python",
        location=Location("app.py", 1, 0, 2, 0),
        parent_id=None,
        signature="def main()",
        visibility=Visibility.PUBLIC,
        modifiers=(),
        content_hash="h1",
    )
    s2 = Symbol(
        id="utils.py::helper",
        name="helper",
        qualified_name="utils.helper",
        kind=SymbolKind.FUNCTION,
        language="python",
        location=Location("utils.py", 1, 0, 2, 0),
        parent_id=None,
        signature="def helper()",
        visibility=Visibility.PUBLIC,
        modifiers=(),
        content_hash="h2",
    )
    g.add_symbol(s1)
    g.add_symbol(s2)
    return g

@pytest.fixture
def sample_override_store():
    """Return clean in-memory OverrideStore."""
    return OverrideStore()
