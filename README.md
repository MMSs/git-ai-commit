# Git AI Commit

An AI-powered Git commit message generator Oh My Zsh plugin that provides
intelligent suggestions based on your staged changes, and integrates seamlessly
with your existing git workflow.

Just stage your changes and type `git commit -m` (or any alias for it) and hit
TAB to generate a commit message.

## Features

- 🤖 Uses GPT-4o to generate contextual commit messages
- 🚀 Fast, streaming suggestions
- 🎯 Supports conventional commit format, gitmoji, and your own custom formats
- ⚙️ Configurable for both global and project-specific settings
- 🔌 Native Oh My Zsh integration

## Prerequisites

- [Oh My Zsh](https://ohmyz.sh/) installed
- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer (recommended)
- OpenAI API key

## Installation

### Quick Install (Recommended)

1. Install `uv` if you haven't already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone this repository in Oh My Zsh's plugins directory:

```bash
git clone https://github.com/MMSs/git-ai-commit.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/git-ai-commit
```

3. Install dependencies using `uv`:

```bash
cd ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/git-ai-commit
uv sync --no-dev
```

4. Add the plugin to your Oh My Zsh configuration. Open your `.zshrc` and add `git-ai-commit` to your plugins:

```bash
plugins=(... git-ai-commit)
```

5. Set your OpenAI API key in your `.zshrc`:

```bash
export OPENAI_API_KEY='your-api-key-here'
```

6. Restart your terminal or reload Oh My Zsh:

```bash
source ~/.zshrc
```

### Alternative: Traditional Installation

If you prefer not to use `uv`, the plugin will automatically create a virtual environment using Python's built-in `venv` and install dependencies with `pip` on first use. Just follow steps 2, 4, 5, and 6 above.

### Updating

To update the plugin:

```bash
cd ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/git-ai-commit
git pull
# Update dependencies
uv sync --no-dev
```

Then restart your terminal or reload Oh My Zsh.

## Configuration

The configuration file is located at `~/.config/git-ai-commit/config.json`. You can also create a project-specific configuration by adding a `.git-ai-commit.json` file to your project root.

```json
{
  "suggestion": {
    "convention": "conventional",
    "format": "multi-line",
    "max_length_per_line": 72
  },
  "openai": {
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 150,
    "streaming": true
  }
}
```

## Usage

1. Stage your changes:

```bash
git add .
```

2. Type `git commit` followed by message flag `-m` or any alias for it and hit TAB to generate a suggestion

3. If you didn't like the suggestion, delete the message and hit TAB again to generate a new suggestion

## Lazygit Integration

You can integrate Git AI Commit with [lazygit](https://github.com/jesseduffield/lazygit) to automatically generate AI-powered commit messages when you commit.

### Setup

This integration uses a Git hook that automatically generates the commit message when you press `c` to commit in lazygit.

1. Create a prepare-commit-msg hook in your repository at `.git/hooks/prepare-commit-msg`:

```bash
#!/bin/bash
COMMIT_MSG_FILE=$1
COMMIT_SOURCE=$2

# Only generate for new commits (not amend, merge, etc.)
if [ -z "$COMMIT_SOURCE" ]; then
    # Check if commit message is empty
    if [ ! -s "$COMMIT_MSG_FILE" ]; then
        PLUGIN_DIR="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/git-ai-commit"

        # Check if we have staged changes
        if ! git diff --cached --quiet; then
            # Generate AI commit message
            source "$PLUGIN_DIR/.venv/bin/activate"
            MSG=$(python3 "$PLUGIN_DIR/src/git_ai_commit.py" 2>/dev/null | sed 's/^ "//;s/"$//')
            deactivate

            # Write the message if generation succeeded
            if [ -n "$MSG" ]; then
                echo "$MSG" > "$COMMIT_MSG_FILE"
            fi
        fi
    fi
fi
```

2. Make the hook executable:

```bash
chmod +x .git/hooks/prepare-commit-msg
```

### Usage in Lazygit

1. Open lazygit in your repository: `lazygit`
2. Stage your changes using the `space` key
3. Press `c` to commit
4. The AI will automatically generate a commit message and populate the editor
5. Review and edit the message if needed
6. Save and close the editor to complete the commit

### Notes

- The AI generation happens automatically when you press `c` to commit
- The generation may take a few seconds depending on the size of your changes
- You can still edit the generated message before finalizing the commit
- The hook only runs for new commits (not for amend, merge commits, etc.)
- The same configuration options from `~/.config/git-ai-commit/config.json` apply
- You'll need to set up this hook for each repository where you want to use it

### Optional: Global Hook Setup

If you want this to work automatically in all your repositories (requires Git 2.9+):

1. Create a global hooks directory:

```bash
mkdir -p ~/.config/git/hooks
```

2. Create `~/.config/git/hooks/prepare-commit-msg` with the same content as above and make it executable:

```bash
chmod +x ~/.config/git/hooks/prepare-commit-msg
```

3. Configure Git to use this hooks directory (this modifies your `~/.gitconfig`):

```bash
git config --global core.hooksPath ~/.config/git/hooks
```

This immediately applies to all your existing and new repositories without needing to run any additional commands.

## Development

If you want to contribute or develop the plugin locally:

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/MMSs/git-ai-commit.git
cd git-ai-commit

# Install dependencies (creates venv automatically and installs everything)
uv sync

# Run tests
uv run pytest

# Format code
uv run black src/

# Lint code
uv run ruff check src/

# Type check
uv run mypy src/
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/MMSs/git-ai-commit.git
cd git-ai-commit

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Known issues

- The plugin doesn't work with `git commit -am` or `git commit -a -m`, you need to stage your changes first.
- If you're using mult-line format, you will see the message twice, this is due to limitation of zsh prompt-reset that resets only the last line of the prompt.

## License

MIT License
