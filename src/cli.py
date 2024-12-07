import asyncio
from typing import Optional
import click
from rich.console import Console
from rich.live import Live
from rich.text import Text

from .config_manager import ConfigManager
from .git_handler import GitHandler
from .ai_suggester import AISuggester

console = Console()


class CommitSuggester:
    def __init__(self):
        self.config = ConfigManager()
        self.git = GitHandler()
        self.ai = AISuggester(self.config)

    async def generate_suggestion(self) -> Optional[str]:
        """Generate a commit message suggestion."""
        try:
            diff = self.git.get_staged_changes()
            if not diff:
                console.print("[yellow]Warning: No staged changes found.[/]")
                return None

            context = self.git.get_repo_context()

            suggestion = Text()
            with Live(suggestion, console=console, refresh_per_second=10) as live:
                async for chunk in self.ai.generate_suggestion(diff, context):
                    suggestion.append(chunk)
                    live.update(suggestion)

            return str(suggestion)

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/]")
            return None


@click.command()
@click.option(
    "--mode", "-m", type=click.Choice(["fast", "quality"]), help="Suggestion mode"
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["single-line", "multi-line"]),
    help="Message format",
)
def main(mode, format):
    """Generate a commit message suggestion based on staged changes."""
    suggester = CommitSuggester()

    if mode:
        suggester.config.config["suggestion"]["mode"] = mode
    if format:
        suggester.config.config["suggestion"]["format"] = format

    try:
        suggestion = asyncio.run(suggester.generate_suggestion())
        if suggestion:
            return 0
        return 1
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/]")
        return 1


if __name__ == "__main__":
    main()
