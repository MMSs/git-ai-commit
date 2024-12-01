from typing import Dict, List, Optional
import git
from pathlib import Path

class GitHandler:
    def __init__(self):
        self.repo = self._get_repo()

    def _get_repo(self) -> git.Repo:
        """Initialize Git repo from current directory."""
        try:
            return git.Repo(Path.cwd(), search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            raise ValueError("Not a git repository")

    def get_staged_changes(self) -> Optional[str]:
        """Get staged changes as a unified diff string."""
        if not self.repo.index.diff("HEAD"):
            return None

        # Get staged changes
        diff = self.repo.git.diff("--cached")
        return diff if diff else None

    def get_staged_files(self) -> List[str]:
        """Get list of staged files."""
        return [item.a_path for item in self.repo.index.diff("HEAD")]

    def get_repo_context(self) -> Dict[str, str]:
        """Get repository context for better commit suggestions."""
        try:
            return {
                "repo_name": Path(self.repo.working_dir).name,
                "current_branch": self.repo.active_branch.name,
                "last_commit_message": str(self.repo.head.commit.message).strip(),
                "unstaged_changes": self.repo.git.diff(),
            }
        except Exception:
            return {}