"""AI agent feedback and repository contribution workflow for codeui."""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from codeui.core.repo import clone_git_repo, get_library_repo_url
from codeui.errors import ContributionError, RepositoryCloneError

class ContributionManager:
    """Manager for AI agents to clone codeui, apply patches, and push modifications.
    Example:
        >>> mgr = ContributionManager()
        >>> mgr.get_repo_url()
        'https://github.com/AAlsubari/codeUI'
    """
    def __init__(
        self,
        repo_url: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        self.repo_url = repo_url or get_library_repo_url()
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def get_repo_url(self) -> str:
        """Get the target GitHub repository URL.
        Example:
            >>> ContributionManager().get_repo_url()
            'https://github.com/AAlsubari/codeUI'
        """
        return self.repo_url

    def _authenticated_url(self, token: Optional[str] = None) -> str:
        auth_token = token or self.token
        url = self.repo_url.strip()
        if auth_token and url.startswith("https://"):
            return url.replace("https://", f"https://x-access-token:{auth_token}@")
        return url

    def clone_repository(
        self,
        target_dir: Optional[Union[str, Path]] = None,
        token: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Path:
        """Clone the codeui library repository into target or temporary directory.
        Example:
            >>> mgr = ContributionManager()
            >>> isinstance(mgr.get_repo_url(), str)
            True
        """
        auth_url = self._authenticated_url(token)
        dest = Path(target_dir) if target_dir else None
        cloned_path, _ = clone_git_repo(auth_url, dest_dir=dest)
        if branch:
            git_bin = shutil.which("git") or "git"
            res = subprocess.run([git_bin, "checkout", branch], cwd=cloned_path, capture_output=True, text=True)
            if res.returncode != 0:
                subprocess.run([git_bin, "checkout", "-b", branch], cwd=cloned_path, capture_output=True, text=True)
        return cloned_path

    def create_feature_branch(self, repo_dir: Union[str, Path], branch_name: str) -> str:
        """Create and checkout a new branch in the cloned repository.
        Example:
            >>> mgr = ContributionManager()
            >>> mgr.clean_branch_name("Fix Bug #1")
            'agent/fix-bug-1'
        """
        git_bin = shutil.which("git") or "git"
        p = Path(repo_dir)
        safe_branch = self.clean_branch_name(branch_name)
        res = subprocess.run([git_bin, "checkout", "-b", safe_branch], cwd=p, capture_output=True, text=True)
        if res.returncode != 0:
            res_co = subprocess.run([git_bin, "checkout", safe_branch], cwd=p, capture_output=True, text=True)
            if res_co.returncode != 0:
                raise ContributionError(f"Failed to create branch '{safe_branch}': {res.stderr.strip()}")
        return safe_branch

    @staticmethod
    def clean_branch_name(name: str) -> str:
        """Convert descriptive name into a git-safe branch identifier.
        Example:
            >>> ContributionManager.clean_branch_name("Fix AST Edge Leak!")
            'agent/fix-ast-edge-leak'
        """
        raw = name.strip().lower()
        if raw.startswith("agent/"):
            raw = raw[6:]
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-")
        if not slug:
            slug = "patch"
        return f"agent/{slug}"

    def apply_changes(self, repo_dir: Union[str, Path], file_changes: Dict[str, str]) -> List[str]:
        """Apply modified or new file contents to the repository on disk.
        Example:
            >>> import tempfile
            >>> with tempfile.TemporaryDirectory() as td:
            ...     mgr = ContributionManager()
            ...     mgr.apply_changes(td, {"test.txt": "hello"})
            ['test.txt']
        """
        p = Path(repo_dir)
        applied: List[str] = []
        for rel_path, content in file_changes.items():
            target = p / rel_path.lstrip("/\\")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            applied.append(rel_path)
        return applied

    def commit_changes(
        self,
        repo_dir: Union[str, Path],
        message: str,
        author_name: str = "CodeUI Agent",
        author_email: str = "agent@codeui.dev",
    ) -> str:
        """Stage all modifications and commit with structured commit message.
        Example:
            >>> mgr = ContributionManager()
            >>> mgr.get_repo_url()
            'https://github.com/AAlsubari/codeUI'
        """
        git_bin = shutil.which("git") or "git"
        p = Path(repo_dir)
        subprocess.run([git_bin, "config", "user.name", author_name], cwd=p, capture_output=True, text=True)
        subprocess.run([git_bin, "config", "user.email", author_email], cwd=p, capture_output=True, text=True)
        subprocess.run([git_bin, "add", "-A"], cwd=p, capture_output=True, text=True)

        res = subprocess.run([git_bin, "commit", "-m", message], cwd=p, capture_output=True, text=True)
        if res.returncode != 0 and "nothing to commit" not in res.stdout.lower() and "nothing to commit" not in res.stderr.lower():
            raise ContributionError(f"Git commit failed: {res.stderr.strip() or res.stdout.strip()}")
        return message

    def push_changes(
        self,
        repo_dir: Union[str, Path],
        remote: str = "origin",
        branch: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Push committed changes to remote repository.
        Example:
            >>> mgr = ContributionManager()
            >>> mgr.get_repo_url()
            'https://github.com/AAlsubari/codeUI'
        """
        git_bin = shutil.which("git") or "git"
        p = Path(repo_dir)
        auth_url = self._authenticated_url(token)

        curr_branch = branch
        if not curr_branch:
            res_b = subprocess.run([git_bin, "rev-parse", "--abbrev-ref", "HEAD"], cwd=p, capture_output=True, text=True)
            curr_branch = res_b.stdout.strip() or "main"

        subprocess.run([git_bin, "remote", "set-url", remote, auth_url], cwd=p, capture_output=True, text=True)
        res_push = subprocess.run([git_bin, "push", "-u", remote, curr_branch], cwd=p, capture_output=True, text=True)

        if res_push.returncode != 0:
            return {
                "success": False,
                "branch": curr_branch,
                "error": res_push.stderr.strip() or res_push.stdout.strip(),
                "message": "Push failed, local commit retained.",
            }
        return {
            "success": True,
            "branch": curr_branch,
            "error": None,
            "message": f"Successfully pushed branch {curr_branch} to {self.repo_url}",
        }

    def submit_contribution(
        self,
        title: str,
        description: str,
        file_changes: Dict[str, str],
        branch_name: Optional[str] = None,
        token: Optional[str] = None,
        push: bool = True,
        workspace_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Execute complete contribution flow: clone, branch, edit, commit, and push.
        Example:
            >>> mgr = ContributionManager()
            >>> isinstance(mgr.get_repo_url(), str)
            True
        """
        temp_dir_obj = None
        if workspace_dir:
            work_path = Path(workspace_dir).resolve()
            work_path.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir_obj = tempfile.TemporaryDirectory(prefix="codeui_contrib_")
            work_path = Path(temp_dir_obj.name).resolve()

        push_result: Dict[str, Any] = {"success": False, "message": "Push disabled by caller"}
        try:
            cloned_repo = self.clone_repository(target_dir=work_path, token=token)
            target_branch = self.create_feature_branch(cloned_repo, branch_name or title)
            applied_files = self.apply_changes(cloned_repo, file_changes)

            commit_msg = f"{title}\n\n{description}\n\nSubmitted by codeui Agent"
            self.commit_changes(cloned_repo, commit_msg)

            if push:
                push_result = self.push_changes(cloned_repo, branch=target_branch, token=token)

            return {
                "status": "pushed" if push_result.get("success") else "committed_locally",
                "repo_url": self.repo_url,
                "branch": target_branch,
                "changed_files": applied_files,
                "commit_message": commit_msg,
                "push_result": push_result,
                "cloned_dir": str(cloned_repo),
            }
        finally:
            if temp_dir_obj and not push_result.get("success"):
                pass
