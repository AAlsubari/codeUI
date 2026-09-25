"""Example 1: Basic Project Scanning and Defect Detection.

This script demonstrates how to scan a project directory using codeui,
extract symbol graphs, and inspect detected code defects.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeui.cli.main import scan_project

def main() -> None:
    # 1. Scan the current project directory
    project_root = Path(".").resolve()
    print(f"Scanning project at: {project_root}")
    
    graph = scan_project(project_root)
    
    # 2. Inspect graph summary
    files = graph.get_all_files()
    symbols = graph.get_all_symbols()
    findings = graph.get_findings()
    
    print(f"\n--- Scan Summary ---")
    print(f"Files Scanned   : {len(files)}")
    print(f"Symbols Extracted: {len(symbols)}")
    print(f"Defects Found   : {len(findings)}")
    
    # 3. List top 5 symbols
    print(f"\n--- Sample Symbols ---")
    for symbol in symbols[:5]:
        print(f"[{symbol.kind.value.upper()}] {symbol.id} ({symbol.visibility.value})")
        if symbol.location:
            print(f"  Location: {symbol.location.file_id}:{symbol.location.start_line}")

    # 4. List detected defects
    if findings:
        print(f"\n--- Detected Defects ---")
        for finding in findings[:5]:
            print(f"[{finding.severity.value.upper()}] {finding.rule_id}: {finding.message}")
            if finding.location:
                print(f"  At: {finding.location.file_id}:{finding.location.start_line}")

if __name__ == "__main__":
    main()
