"""Example 3: AI Agent Context Bundle Builder.

This script demonstrates building dynamic, minimal context bundles for LLM prompts
without token counting overhead, using dependency graph traversal.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeui.cli.main import scan_project
from codeui.agent.context import ContextBuilder, TaskSpec

def main() -> None:
    # 1. Scan project and initialize ContextBuilder
    graph = scan_project(Path(".").resolve())
    builder = ContextBuilder(graph)

    symbol_objects = graph.get_all_symbols()
    files = list(graph.get_all_files())

    if not symbol_objects:
        print("No symbols found.")
        return

    sample_symbol = symbol_objects[0].id
    print(f"Building context bundle for symbol: {sample_symbol}")

    # 2. Build bundle for a specific symbol
    symbol_bundle = builder.for_symbol(sample_symbol, depth=2)
    print("\n--- Symbol Context Bundle JSON ---")
    print(symbol_bundle.to_json()[:500] + "... (truncated)")

    # 3. Build bundle for a high-level task specification
    if files:
        task = TaskSpec(
            query="Fix potential circular imports and handle unhandled exceptions",
            target_files=[files[0]],
        )
        task_bundle = builder.for_task(task, depth=1)
        print("\n--- Task Context Bundle Stats ---")
        print(f"Manifest Info    : {task_bundle.manifest}")
        print(f"Symbols Included : {len(task_bundle.symbol_bodies)}")
        print(f"Signatures Included: {len(task_bundle.cross_signatures)}")
        print(f"Defects Included : {len(task_bundle.findings)}")

if __name__ == "__main__":
    main()
