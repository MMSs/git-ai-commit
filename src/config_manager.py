from pathlib import Path
import yaml
from typing import Any, Dict
from git import Repo, InvalidGitRepositoryError


class ConfigManager:
    def __init__(self):
        self.config = self._load_config()

    def _get_git_root(self) -> Path:
        """Get the root directory of the current git repository."""
        try:
            repo = Repo(Path.cwd(), search_parent_directories=True)
            return Path(repo.working_dir)
        except InvalidGitRepositoryError:
            return Path.cwd()  # Fallback to current directory if not in a git repo

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from multiple sources."""
        # Load default config
        default_config_path = (
            Path(__file__).parent.parent / "config" / "default_config.yaml"
        )
        with open(default_config_path) as f:
            config = yaml.safe_load(f)

        # Load global config if exists
        global_config_path = next(
            (Path.home() / ".config" / "git-ai-commit").glob("config.y*ml"),
            None,
        )

        if global_config_path:
            with open(global_config_path) as f:
                global_config = yaml.safe_load(f)
                config.update(global_config)

        # Load project config if exists, searching from git root
        git_root = self._get_git_root()
        project_config_path = next(git_root.glob(".git-ai-commit.y*ml"), None)
        if project_config_path:
            with open(project_config_path) as f:
                project_config = yaml.safe_load(f)
                config.update(project_config)

        return config

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key_path.split(".")
        value = self.config
        for key in keys:
            try:
                value = value[key]
            except (KeyError, TypeError):
                return default
        return value
