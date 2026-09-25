"""Example 2: Forward and Backward Symbol Tracing.

This script shows how to trace call graphs and symbol dependencies using Tracer.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeui.cli.main import scan_project
from codeui.tracer.tracer import Tracer

def main() -> None:
    # 1. Build universal graph
    graph = scan_project(Path(".").resolve())
    tracer = Tracer(graph)
    
    symbol_objects = graph.get_all_symbols()
    if not symbol_objects:
        print("No symbols found in project.")
        return

    # Select a target symbol
    target_symbol = symbol_objects[0].id
    print(f"Tracing symbol: {target_symbol}")

    # 2. Forward Call Trace (what does this symbol call/depend on?)
    forward_called = list(tracer.forward(target_symbol, depth=3))
    print(f"\n--- Forward Trace (Dependencies) ---")
    print(f"Found {len(forward_called)} downstream dependencies:")
    for sym in forward_called[:10]:
        print(f"  -> {sym.kind.value} {sym.id}")

    # 3. Backward Call Trace (who calls/uses this symbol?)
    backward_callers = list(tracer.backward(target_symbol, depth=3))
    print(f"\n--- Backward Trace (Callers / Dependents) ---")
    print(f"Found {len(backward_callers)} upstream callers:")
    for sym in backward_callers[:10]:
        print(f"  <- {sym.kind.value} {sym.id}")

if __name__ == "__main__":
    main()
