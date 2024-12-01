from typing import AsyncGenerator, Dict
import os
from openai import AsyncOpenAI
from .config_manager import ConfigManager


class AISuggester:
    def __init__(self, config: ConfigManager):
        self.config = config
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.client = AsyncOpenAI(api_key=api_key)

    def _build_prompt(self, diff: str, context: Dict[str, str], mode: str) -> str:
        """Build prompt for the AI model based on diff and context."""
        convention = self.config.get("commit_conventions.current", "conventional")
        format_type = self.config.get("suggestion.format")
        convention_guide = self._get_convention_guide(convention)
        prompt = f"""As a Git commit message generator, analyze these changes and create a {format_type} commit message following the {convention} format.

{convention_guide}

Repository: {context.get('repo_name', 'unknown')}
Branch: {context.get('current_branch', 'unknown')}
Last commit: {context.get('last_commit_message', 'unknown')}

Changes:
{diff}

Unstaged changes:
{context.get('unstaged_changes', 'unknown')}

Generate a {'detailed multi-line' if format_type == 'multi-line' else 'concise single-line'} commit message."""

        return prompt

    def _get_convention_guide(self, convention: str) -> str:
        """Get the convention-specific guide for the prompt."""
        convention_config = self.config.get(f"commit_conventions.conventions.{convention}", {})
        if convention_config:
            convention_guide = ""
            if template := convention_config.get("template"):
                convention_guide += f"Custom template:\n{template}\n\n"
            if types := convention_config.get("types"):
                convention_guide += f"Available types: {', '.join(types)}\n\n"
            if prefixes := convention_config.get("prefixes"):
                convention_guide += f"Available prefixes:\n" + "\n".join(prefixes) + "\n\n"
            return convention_guide
        else:
            raise ValueError(f"No convention configuration found for {convention}")

    async def generate_suggestion(
        self, diff: str, context: Dict[str, str]
    ) -> AsyncGenerator[str, None]:
        """Generate commit message suggestion."""
        if not diff:
            raise ValueError("No staged changes to analyze")

        mode = self.config.get("suggestion.mode")
        model = self.config.get("openai.model")
        temperature = self.config.get("openai.temperature")

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Git commit message generator.",
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(diff, context, mode),
                    },
                ],
                temperature=temperature,
                stream=True,
            )

            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise RuntimeError(f"Failed to generate suggestion: {str(e)}")
