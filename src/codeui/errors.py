"""Typed exception hierarchy for codeui errors."""

class CodeUIError(Exception):
    """Base class for all codeui exceptions.
    Example:
        >>> err = CodeUIError("An error occurred")
        >>> str(err)
        'An error occurred'
    """
    pass

class SymbolNotFoundError(CodeUIError):
    """Raised when a requested symbol cannot be found in the graph.
    Example:
        >>> err = SymbolNotFoundError("sym_123")
        >>> err.symbol_id
        'sym_123'
    """
    def __init__(self, symbol_id: str) -> None:
        super().__init__(f"Symbol not found: {symbol_id}")
        self.symbol_id = symbol_id

class FileNotFoundInGraphError(CodeUIError):
    """Raised when a requested file cannot be found in the graph.
    Example:
        >>> err = FileNotFoundInGraphError("src/index.ts")
        >>> err.file_id
        'src/index.ts'
    """
    def __init__(self, file_id: str) -> None:
        super().__init__(f"File not found in graph: {file_id}")
        self.file_id = file_id

class OverrideConflictError(CodeUIError):
    """Raised when an override target has changed on disk.
    Example:
        >>> err = OverrideConflictError("src/app.ts", "hash_a", "hash_b")
        >>> err.file_path
        'src/app.ts'
    """
    def __init__(self, file_path: str, expected_hash: str, actual_hash: str) -> None:
        super().__init__(f"Override conflict on {file_path}: expected {expected_hash}, got {actual_hash}")
        self.file_path = file_path
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash

class ValidationError(CodeUIError):
    """Raised when edit validation or IR validation fails.
    Example:
        >>> err = ValidationError("Syntax error in edit")
        >>> str(err)
        'Syntax error in edit'
    """
    pass

class SecurityError(CodeUIError):
    """Raised when path traversal or CSRF security checks fail.
    Example:
        >>> err = SecurityError("Path traversal blocked")
        >>> str(err)
        'Path traversal blocked'
    """
    pass

class ParseError(CodeUIError):
    """Raised when language parsing fails.
    Example:
        >>> err = ParseError("main.py", 10, 5, "Unexpected token")
        >>> err.line
        10
    """
    def __init__(self, file_path: str, line: int, col: int, message: str) -> None:
        super().__init__(f"Parse error in {file_path}:{line}:{col}: {message}")
        self.file_path = file_path
        self.line = line
        self.col = col
        self.message = message

class RepositoryCloneError(CodeUIError):
    """Raised when cloning a remote repository fails.
    Example:
        >>> err = RepositoryCloneError("https://github.com/invalid/repo", "fatal: repository not found")
        >>> err.repo_url
        'https://github.com/invalid/repo'
    """
    def __init__(self, repo_url: str, message: str) -> None:
        super().__init__(f"Failed to clone repository '{repo_url}': {message}")
        self.repo_url = repo_url
        self.message = message

class ContributionError(CodeUIError):
    """Raised when AI agent contribution or git mutation fails.
    Example:
        >>> err = ContributionError("Failed to push changes")
        >>> str(err)
        'Failed to push changes'
    """
    pass
