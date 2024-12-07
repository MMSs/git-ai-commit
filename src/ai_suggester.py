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
        convention = self.config.get("suggestion.convention", "conventional")
        format_type = self.config.get("suggestion.format")
        convention_guide = self._get_convention_guide(convention)
        multi_line_prompt = f"""
Generate a multi-line git commit message for the previously mentioned staged changes:

The commit message should include:
1. A short summary ({self.config.get("suggestion.max_length", 50)} characters or less)
2. A detailed description of the changes made
3. References to any related issues or tickets, only if they're present and not already mentioned
4. Use single quotes inside the message, or escape double quotes with a backslash
5. You may mention what changed in each file, but don't repeat yourself

The commit message should **NOT** contain:
1. Code blocks or other formatting
2. markdown formatting
3. backticks
4. References to files that are not mentioned in the diff
5. Double quotes

**Example:**
Add user authentication feature

Implemented user login and registration using JWT tokens.
Added password hashing and validation.
Updated user model to include authentication fields.
"""
        single_line_prompt = f"""
Generate a single-line git commit message for the previously mentioned staged changes:

The commit message should be on one line, concise, and ideally under {self.config.get("suggestion.max_length", 50)} characters.

**Example:**
Add user authentication feature
"""
        prompt = f"""As a Git commit message generator, analyze these changes and create a {format_type} commit message following the {convention} format.  Your response must be in plain text, without any markdown formatting.

{convention_guide}

Repository: {context.get('repo_name', 'unknown')}
Branch: {context.get('current_branch', 'unknown')}

Staged changes:

{diff}


{multi_line_prompt if format_type == 'multi-line' else single_line_prompt}
"""

        return prompt

    def _get_convention_guide(self, convention: str) -> str:
        """Get the convention-specific guide for the prompt."""
        convention_config = self.config.get(
            f"commit_conventions.conventions.{convention}", {}
        )
        if convention_config:
            convention_guide = ""
            if template := convention_config.get("template"):
                convention_guide += f"Custom template:\n{template}\n\n"
            if types := convention_config.get("types"):
                convention_guide += f"Available types: {', '.join(types)}\n\n"
            if prefixes := convention_config.get("prefixes"):
                convention_guide += (
                    f"Available prefixes:\n" + "\n".join(prefixes) + "\n\n"
                )
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
        streaming = self.config.get("openai.streaming", True)

        try:
            prompt = self._build_prompt(diff, context, mode)
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Git commit message generator.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=temperature,
                stream=streaming,

            )

            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise RuntimeError(f"Failed to generate suggestion: {str(e)}")
