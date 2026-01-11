"""Shared fixtures for git-ai-commit tests."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Generator
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def mock_git_repo(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a mock git repository for testing."""
    # Initialize git repo with initial branch name
    subprocess.run(["git", "init", "-b", "main"], cwd=temp_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=temp_dir, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )
    # Disable GPG signing for test commits
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )

    # Create initial commit - this is crucial for HEAD to exist
    readme = temp_dir / "README.md"
    readme.write_text("# Test Project\n\nA test project for git-ai-commit.\n")
    subprocess.run(["git", "add", "README.md"], cwd=temp_dir, capture_output=True, check=True)
    result = subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=temp_dir, capture_output=True
    )
    # Ensure commit succeeded
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create initial commit: {result.stderr.decode()}")

    yield temp_dir


@pytest.fixture
def mock_git_repo_with_changes(mock_git_repo: Path) -> Generator[Path, None, None]:
    """Create a mock git repository with staged changes."""
    # Create a Python file
    src_dir = mock_git_repo / "src"
    src_dir.mkdir()
    py_file = src_dir / "main.py"
    py_file.write_text('def hello():\n    print("Hello, World!")\n')

    # Stage the changes
    subprocess.run(["git", "add", "src/main.py"], cwd=mock_git_repo, capture_output=True)

    yield mock_git_repo


@pytest.fixture
def mock_openai_client() -> MagicMock:
    """Create a mock OpenAI client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "feat: add hello function"
    mock_client.chat.completions.create = MagicMock(return_value=mock_response)
    return mock_client


@pytest.fixture
def mock_async_openai_client():
    """Create a mock async OpenAI client."""

    async def mock_create(**kwargs):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "feat: add hello function"
        return mock_response

    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    return mock_client


@pytest.fixture
def sample_config() -> Dict:
    """Return a sample configuration dictionary."""
    return {
        "suggestion": {
            "convention": "conventional",
            "format": "single-line",
            "max_length_per_line": 72,
        },
        "openai": {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 0,
        },
        "context": {
            "max_input_tokens": 6000,
            "include_commit_history": True,
            "commit_history_count": 5,
            "smart_file_filtering": True,
            "readme_excerpt_lines": 30,
            "detect_tech_stack": True,
            "analyze_branch_name": True,
        },
        "diff_analysis": {
            "extract_functions": True,
            "extract_imports": True,
            "summarize_stats": True,
        },
        "caching": {
            "cache_ttl_minutes": 5,
            "enable_api_prompt_caching": True,
            "enable_local_caching": True,
        },
        "convention_configs": {
            "conventional": {
                "types": ["feat", "fix", "docs", "style", "refactor", "test", "chore"],
                "single-line": {
                    "template": "<type>(<scope>): <description>",
                    "example": "feat(api): add user authentication",
                },
            },
            "gitmoji": {
                "prefixes": ["feat:", "fix:"],
                "single-line": {
                    "template": "<prefix>: <description>",
                    "example": "feat: add feature",
                },
            },
            "traditional": {
                "single-line": {
                    "template": "<description>",
                    "example": "Add feature",
                },
            },
        },
    }


@pytest.fixture
def sample_diff() -> str:
    """Return a sample git diff."""
    return """diff --git a/src/main.py b/src/main.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/main.py
@@ -0,0 +1,5 @@
+def hello():
+    print("Hello, World!")
+
+def goodbye():
+    print("Goodbye!")
"""


@pytest.fixture
def sample_diff_with_tests() -> str:
    """Return a sample git diff that includes test files."""
    return """diff --git a/src/main.py b/src/main.py
index 1234567..abcdef0
--- a/src/main.py
+++ b/src/main.py
@@ -1,2 +1,5 @@
 def hello():
-    print("Hello, World!")
+    return "Hello, World!"
+
+def goodbye():
+    return "Goodbye!"
diff --git a/tests/test_main.py b/tests/test_main.py
new file mode 100644
index 0000000..9876543
--- /dev/null
+++ b/tests/test_main.py
@@ -0,0 +1,8 @@
+from src.main import hello, goodbye
+
+def test_hello():
+    assert hello() == "Hello, World!"
+
+def test_goodbye():
+    assert goodbye() == "Goodbye!"
"""


@pytest.fixture
def temp_cache_dir(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary cache directory."""
    cache_dir = temp_dir / ".cache" / "git-ai-commit"
    cache_dir.mkdir(parents=True)
    yield cache_dir


@pytest.fixture
def temp_config_dir(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary config directory."""
    config_dir = temp_dir / ".config" / "git-ai-commit"
    config_dir.mkdir(parents=True)
    yield config_dir


@pytest.fixture
def project_config_yaml(mock_git_repo: Path) -> Generator[Path, None, None]:
    """Create a project-level YAML config file."""
    config_path = mock_git_repo / ".git-ai-commit.yaml"
    config = {
        "suggestion": {"convention": "gitmoji"},
        "openai": {"model": "gpt-4"},
    }
    config_path.write_text(yaml.dump(config))
    yield config_path


@pytest.fixture
def global_config_yaml(temp_config_dir: Path) -> Generator[Path, None, None]:
    """Create a global YAML config file."""
    config_path = temp_config_dir / "config.yaml"
    config = {
        "suggestion": {"convention": "traditional"},
        "openai": {"temperature": 0.5},
    }
    config_path.write_text(yaml.dump(config))
    yield config_path


@pytest.fixture
def mock_env_vars():
    """Context manager to set and cleanup environment variables."""

    class EnvVarContext:
        def __init__(self):
            self._original = {}

        def set(self, **kwargs):
            for key, value in kwargs.items():
                if key in os.environ:
                    self._original[key] = os.environ[key]
                os.environ[key] = value

        def cleanup(self):
            for key in list(os.environ.keys()):
                if key.startswith("GIT_AI_COMMIT_"):
                    if key in self._original:
                        os.environ[key] = self._original[key]
                    else:
                        del os.environ[key]

    ctx = EnvVarContext()
    yield ctx
    ctx.cleanup()
