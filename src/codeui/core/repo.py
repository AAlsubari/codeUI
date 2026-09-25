"""Git repository cloning and remote URL resolution helper."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from codeui.errors import RepositoryCloneError

DEFAULT_REPOSITORY_URL = "https://github.com/AAlsubari/codeUI"

def get_library_repo_url() -> str:
    """Retrieve the official GitHub repository URL for the codeui library.
    Example:
        >>> get_library_repo_url()
        'https://github.com/AAlsubari/codeUI'
    """
    return os.environ.get("CODEUI_GITHUB_REPO_URL", DEFAULT_REPOSITORY_URL)

def is_git_url(target: str) -> bool:
    """Check if target string represents a remote Git repository URL.
    Example:
        >>> is_git_url("https://github.com/psf/black")
        True
        >>> is_git_url("git@github.com:psf/black.git")
        True
        >>> is_git_url("./local/path")
        False
    """
    if not isinstance(target, str):
        return False
    t = target.strip()
    if t.startswith(("http://", "https://", "git@", "git://", "ssh://")):
        return True
    if t.startswith("github.com/") or t.startswith("gitlab.com/") or t.startswith("bitbucket.org/"):
        return True
    if t.endswith(".git") and (":" in t or "/" in t):
        return True
    return False

def clone_git_repo(repo_url: str, dest_dir: Optional[Path] = None) -> Tuple[Path, Optional[tempfile.TemporaryDirectory]]:
    """Clone a remote Git repository with depth 1 into destination or temporary directory.
    Example:
        >>> is_git_url("https://github.com/example/repo")
        True
    """
    git_bin = shutil.which("git")
    if not git_bin:
        raise RepositoryCloneError(repo_url, "Git executable not found in system PATH")

    url = repo_url.strip()
    if url.startswith("github.com/"):
        url = f"https://{url}"
    elif url.startswith("gitlab.com/"):
        url = f"https://{url}"
    elif url.startswith("bitbucket.org/"):
        url = f"https://{url}"

    temp_obj: Optional[tempfile.TemporaryDirectory] = None
    if dest_dir is None:
        temp_obj = tempfile.TemporaryDirectory(prefix="codeui_repo_")
        target_path = Path(temp_obj.name).resolve()
    else:
        target_path = dest_dir.resolve()
        target_path.mkdir(parents=True, exist_ok=True)

    cmd = [git_bin, "clone", "--depth", "1", "--quiet", url, str(target_path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            if temp_obj:
                temp_obj.cleanup()
            raise RepositoryCloneError(repo_url, res.stderr.strip() or f"Git clone failed with code {res.returncode}")
    except subprocess.TimeoutExpired:
        if temp_obj:
            temp_obj.cleanup()
        raise RepositoryCloneError(repo_url, "Git clone timed out after 120s")
    except Exception as e:
        if temp_obj:
            temp_obj.cleanup()
        if isinstance(e, RepositoryCloneError):
            raise
        raise RepositoryCloneError(repo_url, str(e))

    return target_path, temp_obj
