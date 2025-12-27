import asyncio
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import sys

from openai import AsyncOpenAI


def print_output(message: str, is_error: bool = False) -> None:
    """Print output with space injection and optional error formatting.

    Args:
        message: The message to print.
        is_error: If True, print to stderr (no formatting, handled by zsh).
    """
    if is_error:
        print(message, file=sys.stderr, flush=True)
    else:
        print(f"{message}")


class CacheManager:
    """Manages file-based caching for expensive git operations.

    Provides TTL-based caching with smart invalidation based on
    repository state (branch, HEAD SHA).
    """

    def __init__(self, ttl_minutes: int = 5):
        """Initialize the cache manager.

        Args:
            ttl_minutes: Time-to-live for cached entries in minutes.
        """
        self.ttl_seconds = ttl_minutes * 60
        self.cache_dir = Path.home() / ".cache" / "git-ai-commit"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_file(self, repo_path: str, key: str) -> Path:
        """Get the cache file path for a given repo and key."""
        repo_hash = hashlib.md5(repo_path.encode()).hexdigest()[:12]
        return self.cache_dir / f"{repo_hash}_{key}.json"

    def get(
        self,
        repo_path: str,
        key: str,
        branch: Optional[str] = None,
        head_sha: Optional[str] = None,
    ) -> Optional[Any]:
        """Retrieve a cached value if valid.

        Args:
            repo_path: The repository root path.
            key: The cache key identifier.
            branch: Current branch name for invalidation check.
            head_sha: Current HEAD SHA for invalidation check.

        Returns:
            The cached value if valid, None otherwise.
        """
        cache_file = self._get_cache_file(repo_path, key)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cached = json.load(f)

            # Check TTL
            if time.time() - cached.get("timestamp", 0) > self.ttl_seconds:
                return None

            # Check branch invalidation
            if branch and cached.get("branch") != branch:
                return None

            # Check HEAD SHA invalidation
            if head_sha and cached.get("head_sha") != head_sha:
                return None

            return cached.get("data")

        except (json.JSONDecodeError, IOError):
            return None

    def set(
        self,
        repo_path: str,
        key: str,
        data: Any,
        branch: Optional[str] = None,
        head_sha: Optional[str] = None,
    ) -> None:
        """Store a value in the cache.

        Args:
            repo_path: The repository root path.
            key: The cache key identifier.
            data: The data to cache.
            branch: Current branch name for future invalidation.
            head_sha: Current HEAD SHA for future invalidation.
        """
        cache_file = self._get_cache_file(repo_path, key)

        cache_entry = {
            "timestamp": time.time(),
            "data": data,
        }

        if branch:
            cache_entry["branch"] = branch

        if head_sha:
            cache_entry["head_sha"] = head_sha

        try:
            with open(cache_file, "w") as f:
                json.dump(cache_entry, f)
        except IOError:
            # Silently fail on cache write errors
            pass

    def invalidate(self, repo_path: str, key: Optional[str] = None) -> None:
        """Invalidate cache entries.

        Args:
            repo_path: The repository root path.
            key: Specific key to invalidate. If None, invalidates all for repo.
        """
        if key:
            cache_file = self._get_cache_file(repo_path, key)
            if cache_file.exists():
                cache_file.unlink()
        else:
            # Invalidate all cache entries for this repo
            repo_hash = hashlib.md5(repo_path.encode()).hexdigest()[:12]
            for cache_file in self.cache_dir.glob(f"{repo_hash}_*.json"):
                cache_file.unlink()

    def clear_all(self) -> None:
        """Clear all cache entries."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()


DEFAULT_CONFIG = {
    "suggestion": {
        "convention": "conventional",
        "format": "multi-line",
        "max_length_per_line": 72,
    },
    "openai": {
        "model": "gpt-5-nano",
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
            "types": [
                "feat",
                "feat!",
                "fix",
                "fix!",
                "docs",
                "style",
                "refactor",
                "test",
                "chore",
                "perf",
                "ci",
                "build",
                "revert",
            ],
            "scopes": [],
            "single-line": {
                "template": "<type>(<scope>): <description>",
                "example": "feat(api): add user authentication feature",
            },
            "multi-line": {
                "template": "<type>(<scope>): <description>\\n\\n<body>\\n\\n<footer>",
                "example": "feat(api): add user authentication feature\\n\\n- Implemented user login and registration using JWT tokens.\\n- Added password hashing and validation.\\n- Updated user model to include authentication fields.\\n\\nFixes #123\\nSigned-off-by: John Doe <john.doe@example.com>",
            },
        },
        "gitmoji": {
            "prefixes": [
                "✨ feat:",
                "🐛 fix:",
                "📚 docs:",
                "💄 style:",
                "♻️ refactor:",
                "✅ test:",
                "🔧 chore:",
            ],
            "single-line": {
                "template": "<prefix>: <description>",
                "example": "✨ feat: add user authentication feature",
            },
            "multi-line": {
                "template": "<prefix>: <description>\\n\\n<body>\\n\\n<footer>",
                "example": "✨ feat: add user authentication feature\\n\\n- Implemented user login and registration using JWT tokens.\\n- Added password hashing and validation.\\n- Updated user model to include authentication fields.\\n\\nFixes #123\\nSigned-off-by: John Doe <john.doe@example.com>",
            },
        },
    },
}


class GitAICommit:
    def __init__(self):
        self.config = self._load_config()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.client = AsyncOpenAI(api_key=api_key)

        # Initialize cache manager
        cache_config = self.config.get("caching", {})
        self.cache_enabled = cache_config.get("enable_local_caching", True)
        self.cache = CacheManager(
            ttl_minutes=cache_config.get("cache_ttl_minutes", 5)
        ) if self.cache_enabled else None

    def _load_config(self) -> Dict:
        config = DEFAULT_CONFIG
        config_path = Path.home() / ".config" / "git-ai-commit" / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = {**config, **json.load(f)}
        local_config_path = self._get_repo_path() / ".git-ai-commit.json"
        if local_config_path.exists():
            with open(local_config_path) as f:
                config = {**config, **json.load(f)}
        return config

    def _run_git_command(self, *args) -> str:
        try:
            return subprocess.check_output(["git", *args], text=True)
        except subprocess.CalledProcessError:
            return ""

    def _get_repo_path(self) -> Path:
        return Path(self._run_git_command("rev-parse", "--show-toplevel").strip())

    def detect_tech_stack(self) -> Dict[str, Any]:
        """Detect programming languages and frameworks in the repository.

        Checks for common package/config files to identify the tech stack.

        Returns:
            Dictionary with detected languages, frameworks, and package managers.
        """
        repo_path = self._get_repo_path()

        tech_stack: Dict[str, Any] = {
            "primary_language": None,
            "frameworks": [],
            "package_managers": [],
        }

        # Map of indicator files to (language, package_manager, frameworks)
        indicators = {
            "package.json": ("JavaScript/TypeScript", "npm/yarn", ["Node.js"]),
            "requirements.txt": ("Python", "pip", []),
            "pyproject.toml": ("Python", "pip/poetry", []),
            "Cargo.toml": ("Rust", "Cargo", []),
            "go.mod": ("Go", "Go modules", []),
            "pom.xml": ("Java", "Maven", []),
            "build.gradle": ("Java/Kotlin", "Gradle", []),
            "build.gradle.kts": ("Kotlin", "Gradle", []),
            "composer.json": ("PHP", "Composer", []),
            "Gemfile": ("Ruby", "Bundler", []),
            "mix.exs": ("Elixir", "Mix", []),
            "pubspec.yaml": ("Dart", "pub", ["Flutter"]),
            "Package.swift": ("Swift", "Swift PM", []),
            "Makefile": (None, "Make", []),
            "CMakeLists.txt": ("C/C++", "CMake", []),
        }

        for file, (lang, pm, frameworks) in indicators.items():
            if (repo_path / file).exists():
                if lang and not tech_stack["primary_language"]:
                    tech_stack["primary_language"] = lang
                if pm:
                    tech_stack["package_managers"].append(pm)
                tech_stack["frameworks"].extend(frameworks)

        # Detect specific frameworks from package.json
        package_json_path = repo_path / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path) as f:
                    pkg = json.load(f)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                    framework_indicators = {
                        "react": "React",
                        "vue": "Vue.js",
                        "next": "Next.js",
                        "nuxt": "Nuxt.js",
                        "angular": "Angular",
                        "express": "Express.js",
                        "fastify": "Fastify",
                        "nest": "NestJS",
                        "typescript": "TypeScript",
                    }

                    for dep, framework in framework_indicators.items():
                        if any(dep in d.lower() for d in deps):
                            if framework not in tech_stack["frameworks"]:
                                tech_stack["frameworks"].append(framework)
            except (json.JSONDecodeError, IOError):
                pass

        return tech_stack

    def _git_reponame(self) -> str:
        return Path(self._get_repo_path()).name.strip()

    def analyze_branch_context(self) -> Dict[str, str]:
        """Analyze branch name to extract semantic context.

        Extracts issue references, branch type, and descriptive parts
        from the branch name.

        Returns:
            Dictionary with branch analysis results.
        """
        branch = self._run_git_command("rev-parse", "--abbrev-ref", "HEAD").strip()
        context: Dict[str, str] = {"branch": branch}

        # Extract issue/ticket numbers (GitHub #123 or Jira ABC-123)
        if match := re.search(r"#(\d+)|([A-Z]+-\d+)", branch):
            context["issue_reference"] = match.group(0)

        # Extract branch type from common patterns
        if match := re.match(
            r"^(feature|feat|fix|bugfix|hotfix|docs|refactor|chore|release)/", branch
        ):
            context["branch_type"] = match.group(1)

        # Extract descriptive part (remove type prefix and issue numbers)
        desc = re.sub(r"^(feature|feat|fix|bugfix|hotfix|docs|refactor|chore|release)/", "", branch)
        desc = re.sub(r"[#]?\d+[-_]?", "", desc)
        desc = desc.replace("-", " ").replace("_", " ").strip()
        if desc:
            context["branch_description"] = desc

        return context

    def get_staged_changes(self) -> Optional[str]:
        return self._run_git_command("diff", "--cached", "--unified=10")

    def get_repo_context(self) -> Dict[str, Any]:
        """Get repository context with smart filtering and caching.

        Returns:
            Dictionary with repository context including smart file structure,
            README excerpt, tech stack, and branch analysis.
        """
        context_config = self.config.get("context", {})

        context: Dict[str, Any] = {
            "repo_name": self._git_reponame(),
            "current_branch": self._get_current_branch(),
            "user_name": self._run_git_command("config", "user.name").strip(),
            "user_email": self._run_git_command("config", "user.email").strip(),
        }

        # Use smart file structure if enabled
        if context_config.get("smart_file_filtering", True):
            file_struct = self._get_cached_or_compute(
                "file_structure",
                self.get_smart_file_structure,
                use_head_sha=True,
            )
            context["file_structure"] = file_struct
            # Format for backward compatibility
            context["file_structure_str"] = "\n".join(
                file_struct.get("changed_files", []) +
                file_struct.get("project_files", [])
            )
        else:
            context["file_structure_str"] = self._run_git_command(
                "ls-tree", "--name-only", "-r", "HEAD"
            ).strip()

        # Use README excerpt
        context["readme_content"] = self._get_cached_or_compute(
            "readme_excerpt",
            self.get_relevant_readme_excerpt,
            use_head_sha=True,
        )

        # Add tech stack if enabled
        if context_config.get("detect_tech_stack", True):
            context["tech_stack"] = self._get_cached_or_compute(
                "tech_stack",
                self.detect_tech_stack,
                use_head_sha=False,
            )

        # Add branch analysis if enabled
        if context_config.get("analyze_branch_name", True):
            context["branch_context"] = self.analyze_branch_context()

        # Add recent commits if enabled
        if context_config.get("include_commit_history", True):
            context["recent_commits"] = self._get_cached_or_compute(
                "recent_commits",
                self.get_recent_commits,
                use_head_sha=True,
            )

        return context

    def get_recent_commits(self, count: Optional[int] = None) -> str:
        """Get recent commit messages for few-shot learning.

        Args:
            count: Number of commits to retrieve. Uses config if not specified.

        Returns:
            Formatted string of recent commit messages.
        """
        if count is None:
            count = self.config.get("context", {}).get("commit_history_count", 5)

        commits = self._run_git_command(
            "log",
            f"-{count}",
            "--pretty=format:%s",
            "--no-merges",
        )
        return commits.strip()

    def get_smart_file_structure(self) -> Dict[str, List[str]]:
        """Get filtered file structure focused on changed files.

        Instead of returning the entire file tree, returns only:
        - Changed files and their directories
        - Key project files at the root

        Returns:
            Dictionary with changed_files, changed_directories, and project_files.
        """
        # Get changed files from staged changes
        changed_files = self._run_git_command(
            "diff", "--cached", "--name-only"
        ).strip().split("\n")
        changed_files = [f for f in changed_files if f]

        # Get directories of changed files
        changed_dirs = list(set(str(Path(f).parent) for f in changed_files if f))
        changed_dirs = [d for d in changed_dirs if d != "."]

        # Get key project files at root
        root_patterns = [
            "*.json", "*.toml", "*.yaml", "*.yml",
            "Makefile", "Dockerfile", "*.md",
            "*.lock", ".gitignore",
        ]
        project_files = []
        for pattern in root_patterns:
            files = self._run_git_command(
                "ls-files", "--", pattern
            ).strip().split("\n")
            project_files.extend([f for f in files if f and "/" not in f])

        # Limit project files to avoid bloat
        project_files = project_files[:20]

        return {
            "changed_files": changed_files,
            "changed_directories": changed_dirs,
            "project_files": list(set(project_files)),
        }

    def get_relevant_readme_excerpt(self, max_lines: Optional[int] = None) -> str:
        """Extract relevant sections from README.

        Prioritizes project description and feature sections over
        installation/usage documentation.

        Args:
            max_lines: Maximum lines to extract. Uses config if not specified.

        Returns:
            Extracted README excerpt or "unavailable".
        """
        if max_lines is None:
            max_lines = self.config.get("context", {}).get("readme_excerpt_lines", 30)

        readme_path = self._get_repo_path() / "README.md"
        if not readme_path.exists():
            return "unavailable"

        readme = self._run_git_command("show", "HEAD:README.md").strip()
        if not readme:
            return "unavailable"

        lines = readme.split("\n")

        # Priority sections to extract
        priority_headers = ["# ", "## description", "## about", "## features", "## overview"]
        relevant_lines: List[str] = []
        in_priority_section = False

        for line in lines[:150]:  # Check first 150 lines max
            line_lower = line.lower().strip()

            # Check if this is a priority section header
            if any(line_lower.startswith(h) for h in priority_headers):
                in_priority_section = True
                relevant_lines.append(line)
            elif in_priority_section:
                # Stop at installation/usage/etc sections
                if line_lower.startswith("## ") and any(
                    skip in line_lower for skip in
                    ["install", "usage", "getting started", "prerequisites", "requirements"]
                ):
                    break
                relevant_lines.append(line)

                if len(relevant_lines) >= max_lines:
                    break

        if relevant_lines:
            return "\n".join(relevant_lines)

        # Fallback: return first max_lines lines
        return "\n".join(lines[:max_lines])

    def analyze_diff_semantics(self, diff: str) -> Dict[str, Any]:
        """Analyze diff to extract semantic information.

        Calculates change statistics and identifies types of changes.

        Args:
            diff: The git diff output.

        Returns:
            Dictionary with change statistics and analysis.
        """
        lines = diff.split("\n")

        stats: Dict[str, Any] = {
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
            "test_changes": False,
            "doc_changes": False,
            "config_changes": False,
            "changed_files": [],
        }

        current_file = None
        for line in lines:
            if line.startswith("diff --git"):
                stats["files_changed"] += 1
                # Extract filename
                match = re.search(r"b/(.+)$", line)
                if match:
                    current_file = match.group(1)
                    stats["changed_files"].append(current_file)

                    # Detect change types
                    if "test" in current_file.lower():
                        stats["test_changes"] = True
                    if current_file.endswith((".md", ".rst", ".txt")):
                        stats["doc_changes"] = True
                    if current_file.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".cfg")):
                        stats["config_changes"] = True

            elif line.startswith("+") and not line.startswith("+++"):
                stats["insertions"] += 1
            elif line.startswith("-") and not line.startswith("---"):
                stats["deletions"] += 1

        return stats

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses a rough approximation of ~4 characters per token.

        Args:
            text: The text to estimate tokens for.

        Returns:
            Estimated token count.
        """
        return len(text) // 4

    def _truncate_to_budget(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token budget.

        Args:
            text: The text to truncate.
            max_tokens: Maximum tokens allowed.

        Returns:
            Truncated text within budget.
        """
        estimated = self._estimate_tokens(text)
        if estimated <= max_tokens:
            return text

        # Truncate to approximate character count
        max_chars = max_tokens * 4
        truncated = text[:max_chars]

        # Try to end at a natural boundary
        last_newline = truncated.rfind("\n")
        if last_newline > max_chars * 0.8:
            truncated = truncated[:last_newline]

        return truncated + "\n... (truncated)"

    # === Cache Invalidation Methods ===

    def _get_current_branch(self) -> str:
        """Get the current branch name."""
        return self._run_git_command("rev-parse", "--abbrev-ref", "HEAD").strip()

    def _get_head_sha(self) -> str:
        """Get the current HEAD commit SHA."""
        return self._run_git_command("rev-parse", "HEAD").strip()

    def _get_cache_key(self) -> str:
        """Generate a cache key based on repo path."""
        return str(self._get_repo_path())

    def _should_refresh_cache(self, key: str) -> bool:
        """Check if cache should be refreshed.

        Checks branch and HEAD SHA for invalidation.

        Args:
            key: The cache key to check.

        Returns:
            True if cache should be refreshed, False otherwise.
        """
        if not self.cache_enabled or not self.cache:
            return True

        cached = self.cache.get(
            self._get_cache_key(),
            key,
            branch=self._get_current_branch(),
            head_sha=self._get_head_sha(),
        )
        return cached is None

    def _get_cached_or_compute(
        self,
        key: str,
        compute_fn: callable,
        use_head_sha: bool = False,
    ) -> Any:
        """Get cached value or compute and cache it.

        Args:
            key: The cache key.
            compute_fn: Function to compute the value if not cached.
            use_head_sha: Whether to invalidate on HEAD changes.

        Returns:
            The cached or computed value.
        """
        if not self.cache_enabled or not self.cache:
            return compute_fn()

        repo_path = self._get_cache_key()
        branch = self._get_current_branch()
        head_sha = self._get_head_sha() if use_head_sha else None

        # Try to get from cache
        cached = self.cache.get(repo_path, key, branch=branch, head_sha=head_sha)
        if cached is not None:
            return cached

        # Compute and cache
        result = compute_fn()
        self.cache.set(repo_path, key, result, branch=branch, head_sha=head_sha)
        return result

    # === Prompt Caching Structure Methods ===

    def _build_static_context(self) -> str:
        """Build static context for API prompt caching.

        Returns cacheable context that doesn't change between commits:
        - Repository info
        - Tech stack
        - Recent commits (for style learning)
        - File structure
        - README excerpt

        Returns:
            Formatted static context string.
        """
        context_config = self.config.get("context", {})

        parts = []

        # Repository info
        parts.append(f"Repository: {self._git_reponame()}")

        # Branch context
        if context_config.get("analyze_branch_name", True):
            branch_ctx = self.analyze_branch_context()
            parts.append(f"Branch: {branch_ctx.get('branch', 'unknown')}")
            if issue := branch_ctx.get("issue_reference"):
                parts.append(f"Related Issue: {issue}")
            if branch_type := branch_ctx.get("branch_type"):
                parts.append(f"Branch Type: {branch_type}")

        # Tech stack
        if context_config.get("detect_tech_stack", True):
            tech = self._get_cached_or_compute(
                "tech_stack",
                self.detect_tech_stack,
                use_head_sha=False,
            )
            if tech.get("primary_language"):
                parts.append(f"Language: {tech['primary_language']}")
            if tech.get("frameworks"):
                parts.append(f"Frameworks: {', '.join(tech['frameworks'])}")

        # User info
        parts.append(f"Author: {self._run_git_command('config', 'user.name').strip()}")

        # Recent commits for style learning
        if context_config.get("include_commit_history", True):
            recent = self._get_cached_or_compute(
                "recent_commits",
                self.get_recent_commits,
                use_head_sha=True,
            )
            if recent:
                parts.append("\n## Recent Commit Style Examples")
                parts.append(recent)

        # File structure (smart filtered)
        if context_config.get("smart_file_filtering", True):
            file_struct = self._get_cached_or_compute(
                "file_structure",
                self.get_smart_file_structure,
                use_head_sha=True,
            )
            if file_struct.get("project_files"):
                parts.append("\n## Project Files")
                parts.append("\n".join(file_struct["project_files"]))

        # README excerpt
        readme = self._get_cached_or_compute(
            "readme_excerpt",
            self.get_relevant_readme_excerpt,
            use_head_sha=True,
        )
        if readme != "unavailable":
            parts.append("\n## Project Description")
            parts.append(readme)

        return "\n".join(parts)

    def _build_dynamic_context(self, diff: str) -> str:
        """Build dynamic context for the current commit.

        Returns per-commit context that changes each time:
        - Staged diff
        - Change statistics
        - Changed files list

        Args:
            diff: The git diff output.

        Returns:
            Formatted dynamic context string.
        """
        parts = []

        # Analyze diff
        if self.config.get("diff_analysis", {}).get("summarize_stats", True):
            stats = self.analyze_diff_semantics(diff)
            parts.append("## Change Summary")
            parts.append(f"Files modified: {stats['files_changed']}")
            parts.append(f"Lines added: {stats['insertions']}, removed: {stats['deletions']}")

            if stats.get("test_changes"):
                parts.append("Includes test changes: Yes")
            if stats.get("doc_changes"):
                parts.append("Includes documentation changes: Yes")
            if stats.get("config_changes"):
                parts.append("Includes configuration changes: Yes")

            if stats.get("changed_files"):
                parts.append(f"\nChanged files: {', '.join(stats['changed_files'][:10])}")

        # Apply token budget to diff
        max_tokens = self.config.get("context", {}).get("max_input_tokens", 6000)
        # Reserve tokens for static context (roughly 40% for diff)
        diff_budget = int(max_tokens * 0.5)
        truncated_diff = self._truncate_to_budget(diff, diff_budget)

        parts.append("\n## Staged Changes")
        parts.append("```")
        parts.append(truncated_diff)
        parts.append("```")

        return "\n".join(parts)

    def _get_convention_guide(self, convention: str) -> str:
        """Get the convention-specific guide for the prompt."""
        if convention not in self.config["convention_configs"]:
            raise ValueError(f"Convention '{convention}' does not exist.")
        convention_config = self.config["convention_configs"][convention]
        if convention_config:
            convention_guide = ""
            if template := convention_config.get(
                self.config["suggestion"]["format"], {}
            ).get("template"):
                convention_guide += f"### Template:\\n{template}\\n\\n"
            if example := convention_config.get(
                self.config["suggestion"]["format"], {}
            ).get("example"):
                convention_guide += f"### Example:\\n{example}\\n\\n"
            if types := convention_config.get("types"):
                convention_guide += f"### Available types:\\n{', '.join(types)}\\n\\n"
            if prefixes := convention_config.get("prefixes"):
                convention_guide += (
                    f"### Available prefixes:\\n{', '.join(prefixes)}\\n\\n"
                )
            return convention_guide
        else:
            raise ValueError(
                f"No convention configuration found for {convention}")

    def _build_system_prompt(self) -> str:
        """Build the system prompt with static context for API caching.

        Combines convention guide with static repository context.
        This content is cacheable by OpenAI's prompt caching.

        Returns:
            The system prompt string.
        """
        convention = self.config["suggestion"]["convention"]
        format_type = self.config["suggestion"]["format"]
        convention_guide = self._get_convention_guide(convention)

        prompt_guidance = {
            "multi-line": f"""The commit message should include:
* A short summary (ideally {self.config["suggestion"]["max_length_per_line"]} characters or less)
* The reason for the change if it can be inferred from the context and changes
* References to any related issues or tickets, only if present
* Use single quotes inside the message, or escape double quotes with a backslash
* You may mention what changed in each file, but don't repeat yourself
* Max length per line is {self.config["suggestion"]["max_length_per_line"]} characters
* Don't limit yourself on the count of lines, use as many as needed
* If the changes are too few, use single-line format instead""",
            "single-line": f"The commit message should be on one line, concise, and ideally under {self.config['suggestion']['max_length_per_line']} characters. Describe the reason for the change, or if not possible, describe the changes.",
        }

        # Build static context (cacheable)
        static_context = self._build_static_context()

        return f"""You are a Git commit message generator specializing in {convention} commits.

Generate a {format_type} git commit message. Your response must be in plain text only.

{prompt_guidance.get(format_type, prompt_guidance["single-line"])}

Do NOT use:
- markdown formatting
- code blocks or backticks
- double quotes

## {convention.title()} Convention Guide
{convention_guide}

## Repository Context
{static_context}"""

    def _build_user_prompt(self, diff: str) -> str:
        """Build the user prompt with dynamic context.

        Contains the staged changes and diff analysis.
        This content changes per commit.

        Args:
            diff: The git diff output.

        Returns:
            The user prompt string.
        """
        dynamic_context = self._build_dynamic_context(diff)

        return f"""Generate a commit message for the following changes:

{dynamic_context}

Generate only the commit message. No explanations or additional text."""

    def _build_prompt(self, diff: str, context: Dict[str, Any]) -> str:
        """Build the combined prompt (legacy compatibility).

        This method is kept for backward compatibility but now uses
        the optimized context methods internally.

        Args:
            diff: The git diff output.
            context: The repository context dictionary.

        Returns:
            The combined prompt string.
        """
        convention = self.config["suggestion"]["convention"]
        format_type = self.config["suggestion"]["format"]
        convention_guide = self._get_convention_guide(convention)

        # Format file structure for display
        file_structure = context.get("file_structure_str", "")
        if not file_structure and isinstance(context.get("file_structure"), dict):
            fs = context["file_structure"]
            file_structure = "\n".join(
                fs.get("changed_files", [])[:20] +
                fs.get("project_files", [])[:10]
            )

        # Format tech stack
        tech_info = ""
        if tech := context.get("tech_stack"):
            if tech.get("primary_language"):
                tech_info = f"\n### Tech Stack:\n{tech['primary_language']}"
                if tech.get("frameworks"):
                    tech_info += f" ({', '.join(tech['frameworks'])})"

        # Format branch context
        branch_info = context.get("current_branch", "unknown")
        if branch_ctx := context.get("branch_context"):
            if issue := branch_ctx.get("issue_reference"):
                branch_info += f" (Related: {issue})"

        # Format recent commits
        recent_commits = ""
        if commits := context.get("recent_commits"):
            recent_commits = f"\n### Recent Commits (for style reference):\n{commits}"

        prompt = f"""Generate a {format_type} git commit message following the {convention} format.
Your response must be in plain text, without any markdown formatting.

## Format Requirements
* Max line length: {self.config["suggestion"]["max_length_per_line"]} characters
* Use single quotes or escaped double quotes inside the message

Do NOT use: markdown, code blocks, backticks, or double quotes.

## {convention.title()} Convention
{convention_guide}

## Repository Context
### Repository: {context.get("repo_name", "unknown")}
### Branch: {branch_info}
### Author: {context.get("user_name", "unknown")}{tech_info}{recent_commits}

### Project Files:
{file_structure[:2000] if file_structure else "unavailable"}

### README:
{context.get("readme_content", "unavailable")[:1500]}

## Staged Changes:
```
{diff}
```
"""
        return prompt

    async def generate_suggestion(self) -> Optional[str]:
        """Generate a commit message suggestion using AI.

        Uses static/dynamic context separation for optimal API caching:
        - System message contains static context (cacheable by OpenAI)
        - User message contains dynamic context (diff, stats)

        Returns:
            The generated commit message or None if failed.
        """
        diff = self.get_staged_changes()
        if not diff:
            print_output("No staged changes found.", is_error=True)
            return None

        try:
            cache_config = self.config.get("caching", {})
            use_prompt_caching = cache_config.get("enable_api_prompt_caching", True)

            if use_prompt_caching:
                # Use static/dynamic separation for OpenAI prompt caching
                # System message with static context (cached by OpenAI)
                system_prompt = self._build_system_prompt()
                # User message with dynamic context (changes per commit)
                user_prompt = self._build_user_prompt(diff)
            else:
                # Legacy mode: single combined prompt
                system_prompt = "You are a Git commit message generator specializing in conventional commits and gitmoji formats."
                user_prompt = self._build_prompt(diff, self.get_repo_context())

            # Build API parameters
            model = self.config["openai"]["model"]
            api_params: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }

            # Only set max_completion_tokens if explicitly configured (0 = no limit)
            max_tokens = self.config["openai"].get("max_tokens", 0)
            if max_tokens > 0:
                api_params["max_completion_tokens"] = max_tokens

            # Some models don't support custom temperature
            # - Reasoning models (o1, o3, o4): no temperature support
            # - GPT-5 series: only default (1) supported
            no_temp_models = ("o1", "o3", "o4", "gpt-5")
            if not any(model.startswith(prefix) for prefix in no_temp_models):
                api_params["temperature"] = self.config["openai"].get("temperature", 0.7)

            response = await self.client.chat.completions.create(**api_params)

            suggestion = response.choices[0].message.content or ""
            print_output(f'"{suggestion}"')

            return suggestion

        except Exception as e:
            print_output(f"Error: {str(e)}", is_error=True)
            return None


def main():
    committer = GitAICommit()

    try:
        suggestion = asyncio.run(committer.generate_suggestion())
        return 0 if suggestion else 1
    except Exception as e:
        print_output(f"Error: {str(e)}", is_error=True)
        return 1


if __name__ == "__main__":
    exit(main())
