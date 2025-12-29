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

## Git Hook Integration

You can use a `prepare-commit-msg` hook to automatically generate commit messages when running `git commit` (without a message). This works with any tool that uses Git's standard commit flow.

### Setup

1. Create a global hooks directory:

```bash
mkdir -p ~/.config/git/hooks
```

2. Create or update `~/.config/git/hooks/prepare-commit-msg`:

```bash
#!/bin/bash
COMMIT_MSG_FILE=$1
COMMIT_SOURCE=$2

# Only generate for new commits (not amend, merge, etc.)
if [ -z "$COMMIT_SOURCE" ]; then
    # Check if commit message has no actual content (only comments or empty)
    if ! grep -q '^[^#]' "$COMMIT_MSG_FILE" 2>/dev/null; then
        PLUGIN_DIR="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/git-ai-commit"

        # Check if we have staged changes
        if ! git diff --cached --quiet; then
            # Use ANSI escape codes for colors (bash-compatible, portable across shells)
            # Hook scripts run in various environments, so we use standard ANSI codes
            # instead of shell-specific features like zsh's terminfo module
            # Show loading message
            echo -e "\033[33m🤖 Generating AI commit message...\033[0m" >&2

            # Generate AI commit message with timing
            START_TIME=$(date +%s)

            # Use uv run if available, otherwise use venv
            if command -v uv &>/dev/null && [ -d "$PLUGIN_DIR/.venv" ]; then
                MSG=$(uv run --project "$PLUGIN_DIR" python "$PLUGIN_DIR/src/git_ai_commit.py" 2>&1)
            else
                MSG=$(
                    source "$PLUGIN_DIR/.venv/bin/activate" || exit 1
                    python3 "$PLUGIN_DIR/src/git_ai_commit.py" 2>&1
                    exit_code=$?
                    deactivate
                    exit $exit_code
                )
            fi
            EXIT_CODE=$?

            END_TIME=$(date +%s)
            DURATION=$((END_TIME - START_TIME))

            # Write the message if generation succeeded
            if [ $EXIT_CODE -eq 0 ] && [ -n "$MSG" ]; then
                echo "$MSG" > "$COMMIT_MSG_FILE"
                echo -e "\033[32m✓ Commit message generated in ${DURATION}s\033[0m" >&2
            else
                echo -e "\033[31m✗ Failed to generate commit message\033[0m" >&2
            fi
        fi
    fi
fi
```

3. Make the hook executable:

```bash
chmod +x ~/.config/git/hooks/prepare-commit-msg
```

4. Configure Git to use this hooks directory:

```bash
git config --global core.hooksPath ~/.config/git/hooks
```

### Usage

1. Stage your changes: `git add .`
2. Run `git commit` (without `-m` flag)
3. The hook will generate an AI commit message and open your editor with it pre-filled
4. Review, edit if needed, and save to complete the commit

### Notes

- The hook works with `git commit` but **not** with `git commit --verbose`, as these set `$COMMIT_SOURCE` to a non-empty value and append the full diff to the template.
- For aliases like `gcmsg` that use `git commit -m`, use the TAB key integration instead
- The hook only runs for new commits (not for amend, merge, etc.)

## Lazygit Integration

You can integrate Git AI Commit with [lazygit](https://github.com/jesseduffield/lazygit) using a custom command that generates commit messages on demand.

### Setup

1. Open lazygit: `lazygit`
2. Navigate to the **Status** panel (press `1` or use arrow keys)
3. Press `e` to edit the config file
4. Add the following custom command:

```yaml
customCommands:
  - key: "<c-g>"
    description: "Generate AI commit message"
    context: "files"
    output: "terminal"
    command: >
      bash {{path-to-git-ai-commit-plugin}}/bin/lazygit-generate-commit.sh
```

Replace `{{path-to-git-ai-commit-plugin}}` with the actual path, typically:
- `$HOME/.oh-my-zsh/custom/plugins/git-ai-commit` for standard Oh My Zsh installations
- `${ZSH_CUSTOM}/plugins/git-ai-commit` if you have a custom ZSH_CUSTOM path

5. Save the file and restart lazygit

### Usage in Lazygit

1. Stage your changes using `space`
2. Press `Ctrl+G` to generate an AI commit message
3. Your editor opens with the generated message
4. Edit if needed, save and close to commit (or clear the file to abort)

### Notes

- The script is located in `bin/lazygit-generate-commit.sh` within the plugin directory
- Uses `$EDITOR` environment variable (defaults to `nvim`)
- `output: "terminal"` suspends lazygit and runs the command in a terminal
- The script includes trap handlers for proper cleanup of temporary files

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
