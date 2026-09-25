# Static Analyzer & Defect Reference

`codeui` includes 8 built-in static defect analyzers that operate on the universal intermediate representation (IR) graph without executing target project code.

---

## 1. Undefined Identifier Rule (`undefined`)
- **Description**: Detects references to symbols or functions that are neither defined in the local module, explicitly imported, nor recognized as language built-ins.
- **Severity**: `Error`
- **Use Case**: Catches typos, missing imports, and broken function calls early.

---

## 2. Dead Code Rule (`dead_code`)
- **Description**: Identifies unreferenced private functions, uncalled helper routines, and unused module exports across the codebase.
- **Severity**: `Warning`
- **Use Case**: Helps maintain clean codebases by flagging abandoned or unreachable code.

---

## 3. Unresolved Import Rule (`unresolved_import`)
- **Description**: Validates import statements against the project filesystem structure, manifest files, and known module files.
- **Severity**: `Error`
- **Use Case**: Flags broken relative imports, missing modules, or missing dependencies before runtime execution.

---

## 4. Circular Dependency Rule (`circular`)
- **Description**: Detects dependency cycles across modules and packages using Tarjan's Strongly Connected Components (SCC) algorithm.
- **Severity**: `Warning` / `Error`
- **Use Case**: Prevents tight coupling, initialization order bugs, and import recursion errors.

---

## 5. Structural Code Duplicates Rule (`duplicates`)
- **Description**: Identifies structural code clones and duplicate function implementations using k-shingle token hashing.
- **Severity**: `Info` / `Warning`
- **Use Case**: Promotes code deduplication and refactoring into shared helper functions.

---

## 6. Unreachable Statement Rule (`unreachable`)
- **Description**: Flags code blocks and statements positioned directly after terminal control flow statements (`return`, `raise`, `break`, `continue`, `sys.exit`).
- **Severity**: `Warning`
- **Use Case**: Cleans up dead execution paths following control jumps.

---

## 7. Variable Shadowing Rule (`shadowing`)
- **Description**: Highlights local variables or parameters that shadow outer-scope symbols, built-in identifiers, or global constants.
- **Severity**: `Info` / `Warning`
- **Use Case**: Prevents confusing variable scoping bugs.

---

## 8. API Drift Rule (`api_drift`)
- **Description**: Compares exported function and class signatures against a stored baseline graph snapshot to detect breaking interface changes.
- **Severity**: `Warning` / `Error`
- **Use Case**: Ensures backward compatibility across library releases and API boundaries.
