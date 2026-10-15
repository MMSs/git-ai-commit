# Git AI Commit

An AI-powered Git commit message generator Oh My Zsh plugin that provides
intelligent suggestions based on your staged changes, and integrates seamlessly
with your existing git workflow.

Just stage your changes and type `git commit -m` (or any alias for it) and hit
TAB to generate a commit message.

## Features

- 🤖 Uses GPT-6 Luna by default to generate contextual commit messages
- 🚀 Fast suggestions with configurable reasoning effort
- 🎯 Supports conventional commit format, gitmoji, and your own custom formats
- ⚙️ Configurable for both global and project-specific settings
- 🔌 Native Oh My Zsh integration

## Prerequisites

- [Oh My Zsh](https://ohmyz.sh/) installed
- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer (recommended)
- OpenAI API key, or a local AI CLI (Claude Code, Codex, Cursor Agent, Ollama, …)

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
UV_PROJECT_ENVIRONMENT="$PWD/.venv" uv sync --no-dev --locked
```

4. Add the plugin to your Oh My Zsh configuration. Open your `.zshrc` and add `git-ai-commit` to your plugins:

```bash
plugins=(... git-ai-commit)
```

5. Set your OpenAI API key in your `.zshrc` (skip if you only use a local CLI):

```bash
export OPENAI_API_KEY='your-api-key-here'
```

6. Restart your terminal or reload Oh My Zsh:

```bash
source ~/.zshrc
```

### Alternative: Traditional Installation

If you prefer not to use `uv`, the plugin will automatically create a virtual environment using Python's built-in `venv` and install dependencies with `pip` on first use. Just follow steps 2, 4, 5, and 6 above.

Setup uses dependency requirements from `pyproject.toml` and `uv.lock`. After a
successful install, a checksum marker avoids Python version probes and repeat
installs on shell startup. Changes to either dependency file trigger one refresh.
uv always targets the plugin's `.venv`, regardless of `UV_PROJECT_ENVIRONMENT`.
Generation uses that interpreter directly, without another dependency sync.

Failed installs are remembered for 24 hours for the same dependency revision.
The next shell startup after that interval retries automatically; another failure
starts a new 24-hour wait. A runnable existing environment remains available; a
failed fresh install cannot load the plugin even if it created an interpreter.
To retry sooner, run the command below. Repairing setup does not finish loading
the plugin in the current shell, so reload it afterward to enable TAB:

```zsh
_git_ai_commit_ensure_venv --retry
# Reload after repairing a setup failure:
source "$PLUGIN_DIR/git-ai-commit.plugin.zsh"
```

### Updating

To update the plugin:

```bash
cd ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/git-ai-commit
git pull
# Update dependencies
UV_PROJECT_ENVIRONMENT="$PWD/.venv" uv sync --no-dev --locked
```

Then restart your terminal or reload Oh My Zsh.

Existing model overrides survive updates. Check both
`~/.config/git-ai-commit/config.yaml` and your repository's `.git-ai-commit.yaml`;
the repository override takes precedence over global settings and shipped defaults.

## Configuration

The configuration file is located at `~/.config/git-ai-commit/config.yaml`. You can also create a project-specific configuration by adding a `.git-ai-commit.yaml` file to your project root.

**Note**: Both `.yaml` and `.yml` extensions are supported.

```yaml
# Commit message suggestion settings
suggestion:
  convention: conventional  # Options: conventional, gitmoji, traditional
  format: multi-line       # Options: single-line, multi-line
  max_length_per_line: 72

# Where messages come from: api (default) or command
backend: api

# API backend settings
api:
  provider: openai
  model: gpt-6-luna
  reasoning_effort: none  # Lowest latency; translated automatically per model
  temperature: 0.7
  max_tokens: 0  # 0 = model output limit; positive limits include reasoning tokens
```

Older configs with a top-level `openai:` section keep working; they are read as `api:`.

See [config/default_config.yaml](config/default_config.yaml) for all available configuration options with detailed comments.

### Recommended Models

Model guidance checked against official OpenAI documentation on October 14, 2026.

| Model | Suggested use | Suggested effort |
|-------|---------------|------------------|
| `gpt-6-luna` | Default: fast, inexpensive commit summaries and continuations | `none` |
| `gpt-6.1-sol` | Complex changes that benefit from deeper reasoning | `low` |
| `gpt-6-astra` | Most demanding changes when quality matters more than cost | `low` |
| `gpt-5.4-mini` | Alternative within the GPT-5 family | `none` |

These recommendations follow OpenAI's [model guidance](https://developers.openai.com/api/docs/guides/latest-model).
GPT-4o and GPT-4.1 families are deprecated with a January 14, 2027 shutdown;
GPT-5.4 nano is deprecated with an April 1, 2027 shutdown. Prefer GPT-6 Luna for
migrations. See the [deprecation schedule](https://developers.openai.com/api/docs/deprecations).

### API and Effort Compatibility

Generation and partial-message completion both use Chat Completions without tools.
The recommended models support this API; switching to Responses is unnecessary
for this workflow. Tool calling has additional restrictions documented in the
[GPT-6 migration guide](https://developers.openai.com/api/docs/guides/latest-model#update-api-and-model-parameters).
Unlisted models, including `gpt-5-chat-latest` and `gpt-5.1-chat-latest`, pass
through with no temperature or effort parameter. This preserves API defaults
without guessing capabilities. The API still decides whether a model is available
and supports Chat Completions; passing through does not enable Responses-only models.

| Supported models | API effort values |
|------------------|-------------------|
| `gpt-5`, `gpt-5-mini`, `gpt-5-nano` | `minimal`, `low`, `medium`, `high` |
| `gpt-5.1` | `none`, `low`, `medium`, `high` |
| `gpt-5.2`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.5` | `none`, `low`, `medium`, `high`, `xhigh` |
| `gpt-5.6`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-6-sol`, `gpt-6-luna` | `none`, `low`, `medium`, `high`, `xhigh`, `max` |
| `gpt-6.1-sol`, `gpt-6-astra` | `low`, `medium`, `high`, `xhigh`, `max` |

Dated snapshots of listed models use the same compatibility rules while preserving
the exact model ID sent to the API. Compatibility support does not guarantee that
deprecated models or specific snapshots remain available to your API account.

Effort translates automatically:

- Supported settings remain unchanged.
- `none` becomes `minimal` for original GPT-5, or `low` for GPT-6 Astra and GPT-6.1 Sol.
- `minimal` becomes `low` on models that do not support it.
- `xhigh`/`max` above a model's supported range become its highest supported effort.
- Missing, null, empty, or `false` effort omits the API parameter. This differs from
  the string `none`, which explicitly requests no reasoning where supported.
  Config merging normally supplies the shipped `none` value when an override
  omits the setting; use `null` or `false` to override it and retain API defaults.
- Unrecognized effort values fail for listed reasoning models. `o1`, `o3`,
  `o3-mini`, and `o4-mini` normalize explicit effort to `low`, `medium`, or `high`.
  `o1-mini` and unknown models never receive effort.

Temperature is sent for GPT-5.1+ and GPT-6 only when the translated effort is `none`.
Original GPT-5, o-series, and unknown models omit it. GPT-3.5/GPT-4 families retain
configured temperature, including GPT-4o and GPT-4o mini. Omitting effort also
omits temperature for listed reasoning models.
`max_tokens` is sent as `max_completion_tokens` and limits both reasoning and
visible output. A value of `0`, `null`, or an empty value omits the parameter.
Integer strings such as `"500"` are accepted; invalid values report a clear
`max_tokens` configuration error.

Sources: [GPT-5](https://developers.openai.com/api/docs/models/gpt-5),
[GPT-5.1](https://developers.openai.com/api/docs/models/gpt-5.1),
[GPT-5.2](https://developers.openai.com/api/docs/models/gpt-5.2),
[GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5),
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
and [migration guidance](https://developers.openai.com/api/docs/guides/latest-model).

## Local CLI Backends

Instead of calling the OpenAI API, git-ai-commit can run any local AI CLI you already use. Set `backend: command` and describe the command:

```yaml
backend: command
command:
  argv: ["claude", "-p", "--output-format", "text", "--model", "haiku"]
  timeout_seconds: 60
```

`argv` runs directly, never through a shell, in an empty temporary directory. All repository context is already in the prompt, so the CLI does not need to read your files.

| Placeholder | Meaning | If absent |
|---|---|---|
| `{prompt}` | Prompt as an argument | Prompt is sent on stdin (recommended: large diffs can exceed argument limits) |
| `{system_prompt}` | System prompt as an argument | System prompt is prepended to the prompt |
| `{output_file}` | Temp file the CLI writes its answer to | stdout is read |

Switch backends without editing config:

```bash
export GIT_AI_COMMIT_BACKEND=command   # this shell
git-ai-commit --backend api            # one manual run
```

Precedence: `--backend` > `GIT_AI_COMMIT_BACKEND` > project config > global config > `api`. `OPENAI_API_KEY` is only needed for the `api` backend.

Local CLIs start slower than an API call (often several seconds) and do not use OpenAI prompt caching. Pick a small, fast model. On timeout or Ctrl+C the CLI and any processes it started are stopped.

### Recipes

Flags change between releases; check `<tool> --help` if a recipe stops working.

**Claude Code** (tools disabled, system prompt passed separately):

```yaml
command:
  argv: ["claude", "-p", "--output-format", "text", "--model", "haiku",
         "--tools", "", "--system-prompt", "{system_prompt}"]
```

**Codex** (read-only sandbox, answer read from a file):

```yaml
command:
  argv: ["codex", "exec", "-c", "model_reasoning_effort=low", "-s", "read-only",
         "--skip-git-repo-check", "-o", "{output_file}", "-"]
```

Add `"-m", "<model>"` to pick a model; ChatGPT-account logins accept fewer models than API-key logins.

**Cursor Agent**:

```yaml
command:
  argv: ["cursor-agent", "-p", "--output-format", "text", "--model", "auto",
         "{prompt}"]
```

**Ollama** (fully local):

```yaml
command:
  argv: ["ollama", "run", "--hidethinking", "qwen3:8b"]
  timeout_seconds: 120
```

## Usage

1. Stage your changes:

```bash
git add .
```

2. Type `git commit` followed by message flag `-m` or any alias for it and hit TAB to generate a suggestion

3. If you didn't like the suggestion, delete the message and hit TAB again to generate a new suggestion

## Message Completion Mode

In addition to generating complete commit messages, you can start typing your own message and press TAB to have AI continue from where you left off. This is perfect when you want to establish the message structure yourself but need help completing it.

### How It Works

**Generation Mode** (complete message):
```bash
git commit -m <TAB>
# AI generates: git commit -m "feat: add user authentication with JWT tokens"
```

**Completion Mode** (partial message):
```bash
# You start typing
git commit -m "feat(auth): this feature introduces <TAB>
# AI continues: git commit -m "feat(auth): this feature introduces secure JWT-based authentication for API endpoints

# Press TAB again to continue
<TAB>
# AI extends: git commit -m "feat(auth): this feature introduces secure JWT-based authentication for API endpoints with refresh token support

# Close quote when satisfied
"
```

### Key Features

- **Style Matching**: AI automatically matches your writing style and convention, ignoring your configured convention setting
- **Iterative Completion**: Press TAB multiple times to progressively build your message
- **No Quote Required**: Start typing with just `git commit -m "your text` - the quote stays open after each completion
- **Works with Aliases**: Compatible with all git aliases (`gcmsg`, `gc`, etc.)

### Examples

**Conventional Commits**:
```bash
git commit -m "fix(api): resolve issue with <TAB>
# → git commit -m "fix(api): resolve issue with rate limiting in payment endpoints
```

**Gitmoji Style**:
```bash
git commit -m "✨ Add new <TAB>
# → git commit -m "✨ Add new dashboard component with real-time analytics
```

**Custom Style**:
```bash
git commit -m "Update README to include <TAB>
# → git commit -m "Update README to include installation instructions and usage examples
```

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

            # Reuse plugin dependencies without syncing during commit generation
            MSG=$("$PLUGIN_DIR/.venv/bin/python" "$PLUGIN_DIR/src/git_ai_commit.py" 2>&1)
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
- If the plugin environment is missing, the script prints the setup command
  before attempting generation; initializing the zsh plugin also creates it.

## Development

If you want to contribute or develop the plugin locally:

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/MMSs/git-ai-commit.git
cd git-ai-commit

# Install dependencies (creates venv automatically and installs everything)
uv sync --extra dev

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
