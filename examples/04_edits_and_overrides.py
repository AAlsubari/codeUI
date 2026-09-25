"""Example 4: Edits, Non-Destructive Overrides, and Direct Disk Layer.

This script demonstrates applying file edits non-destructively using OverrideStore
or saving changes directly to disk using EditTools.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeui.core.graph import Graph
from codeui.core.override import OverrideStore
from codeui.agent.edit_tools import EditTools

def main() -> None:
    project_root = Path(".").resolve()
    graph = Graph()
    store = OverrideStore()

    # 1. Non-destructive Override Store Mode (Direct Disk = False)
    print("--- Mode 1: Non-destructive Override Store ---")
    tools_shadow = EditTools(graph, store, project_root=project_root, direct_disk=False)
    
    file_path = "sample_test_file.py"
    sample_content = "# Sample file content for override\ndef hello():\n    return 'world'\n"
    
    proposal = tools_shadow.replace_file(file_path, sample_content)
    tools_shadow.apply(proposal, write_to_disk=False)
    
    print(f"Shadow edit stored for {file_path}")
    print("Active unified diff:")
    print(store.to_diff())

    # 2. Direct Disk Edit Mode (Direct Disk = True)
    print("\n--- Mode 2: Direct Disk Write Mode ---")
    tools_disk = EditTools(graph, store, project_root=project_root, direct_disk=True)
    
    target_disk_file = project_root / ".codeui" / "example_disk_edit.txt"
    target_disk_file.parent.mkdir(exist_ok=True)
    
    disk_proposal = tools_disk.replace_file(str(target_disk_file), "Direct disk edit content line 1\nLine 2\n")
    saved_path = tools_disk.apply_to_disk(disk_proposal)
    
    print(f"Successfully wrote directly to disk at: {saved_path}")
    if saved_path.exists():
        print(f"File content on disk:\n{saved_path.read_text(encoding='utf-8')}")
        saved_path.unlink()  # Clean up demo file

if __name__ == "__main__":
    main()
