"""Example 5: Agent Automated Contribution & Repository Self-Improvement.

This script shows how AI agents utilizing codeui can automatically clone
the codeui repository (https://github.com/AAlsubari/codeUI), apply proposed fixes or enhancements,
create feature branches, and submit contributions.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeui.agent.contribution import ContributionManager
from codeui.core.repo import get_library_repo_url
from codeui.errors import RepositoryCloneError

def main() -> None:
    # 1. Dynamically retrieve codeui repository URL
    repo_url = get_library_repo_url()
    print(f"codeui Repository Target: {repo_url}")

    # 2. Instantiate ContributionManager
    # Note: Pass a GitHub PAT token in environment variable GITHUB_TOKEN if pushing
    github_token = os.environ.get("GITHUB_TOKEN")
    mgr = ContributionManager(token=github_token)

    # 3. Define automated contribution payload
    contribution_title = "Agent Docstring Enhancement"
    description = "Automated improvement adding doctest examples to public functions."
    file_changes = {
        "docs/agent_integration.md": "# Updated Agent Integration Guide\n\nAI agents can contribute automatically via ContributionManager.\n"
    }

    print("\nsubmitting contribution (local branch creation & commit)...")
    try:
        # Set push=False for dry-run / local commit validation
        result = mgr.submit_contribution(
            title=contribution_title,
            description=description,
            file_changes=file_changes,
            token=github_token,
            push=False,  # Set to True when token is configured with write access to push
        )

        print("\n--- Contribution Results ---")
        print(f"Status       : {result['status']}")
        print(f"Branch       : {result['branch']}")
        print(f"Target Repo  : {result['repo_url']}")
        print(f"Changed Files: {result['changed_files']}")
        print(f"Message      : {result['message']}")
    except RepositoryCloneError as ex:
        print(f"\n[Note] Could not clone remote repo '{repo_url}' in offline environment: {ex}")
        print("To push contributions to GitHub, ensure internet access and set GITHUB_TOKEN.")

if __name__ == "__main__":
    main()
