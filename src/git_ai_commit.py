import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional
import sys

from openai import AsyncOpenAI


DEFAULT_CONFIG = {
    "suggestion": {
        "convention": "conventional",
        "format": "multi-line",
        "max_length_per_line": 72,
    },
    "openai": {
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 150,
        "streaming": True,
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

    def _git_reponame(self) -> str:
        return Path(self._get_repo_path()).name.strip()

    def get_staged_changes(self) -> Optional[str]:
        return self._run_git_command("diff", "--cached", "--unified=3")

    def get_repo_context(self) -> Dict[str, str]:
        return {
            "repo_name": self._git_reponame(),
            "current_branch": self._run_git_command(
                "rev-parse", "--abbrev-ref", "HEAD"
            ).strip(),
            "file_structure": self._run_git_command("ls-tree", "--name-only", "-r", "HEAD").strip(),
            "readme_content": self._run_git_command("show", "HEAD:README.md").strip() if Path(self._get_repo_path() / "README.md").exists() else "unavailable",
            "user_name": self._run_git_command("config", "user.name").strip(),
            "user_email": self._run_git_command("config", "user.email").strip(),
        }

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
            raise ValueError(f"No convention configuration found for {convention}")

    def _build_prompt(self, diff: str, context: Dict[str, str]) -> str:
        convention = self.config["suggestion"]["convention"]
        format_type = self.config["suggestion"]["format"]
        convention_guide = self._get_convention_guide(convention)
        prompt_expantion = {
            "multi-line": f"""The commit message should include:
* A short summary (ideally {self.config["suggestion"]["max_length_per_line"]} characters or less)
* The reason for the change if you can be inferred from the context and changes
* References to any related issues or tickets, only if they're present and not already mentioned
* Use single quotes inside the message, or escape double quotes with a backslash
* You may mention what changed in each file, but don't repeat yourself
* Max length per line is {self.config["suggestion"]["max_length_per_line"]} characters
* Don't limit yourself on the count of lines, you can use as many as you need to describe the changes
* If the changes are too few, you can use the single-line format
""",
            "single-line": f"The commit message should be on one line, concise, and ideally under {self.config["suggestion"]["max_length_per_line"]} characters, and it should preferably describe the reason for the change, or if not possible, describe the changes.",
        }
        prompt = f"""As a Git commit message generator, analyze the repository context, try to infer the framework or language of the project from the repository context, file structure, and README, and understand the purpose of the repository and whether it's a monorepo or not, and the changes you're about to commit, and generate a {format_type} git commit message following the {convention} format.  Your response must be in plain text, without any markdown formatting.

{prompt_expantion[format_type]}

Do **not** use:
- markdown formatting
- code blocks
- backticks
- double quotes

## {convention} convention guide
{convention_guide}

## Context
### Repository:
{context.get('repo_name', 'unknown')}
### Branch:
{context.get('current_branch', 'unknown')}
### User:
{context.get('user_name', 'unknown')}
### Email:
{context.get('user_email', 'unknown')}
### File structure:
````
{context.get('file_structure', 'unavailable')}
````
### README file:
````
{context.get('readme_content', 'unavailable')}
````

## Staged changes:
````
{diff}
````
"""
        return prompt

    async def generate_suggestion(self) -> Optional[str]:
        diff = self.get_staged_changes()
        if not diff:
            print("No staged changes found.")
            return None

        try:
            response = await self.client.chat.completions.create(
                model=self.config["openai"]["model"],
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Git commit message generator specializing in conventional commits and gitmoji formats.",
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(diff, self.get_repo_context()),
                    },
                ],
                temperature=self.config["openai"]["temperature"],
                max_tokens=self.config["openai"]["max_tokens"],
                stream=self.config["openai"]["streaming"],
            )

            suggestion = ""
            print(' "', end="", flush=True)  # Print opening quote
            async for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    suggestion += content
                    print(content, end="", flush=True)
            print('"')  # Print closing quote
            return suggestion

        except Exception as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            return None


def main():
    committer = GitAICommit()

    try:
        suggestion = asyncio.run(committer.generate_suggestion())
        return 0 if suggestion else 1
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main())
