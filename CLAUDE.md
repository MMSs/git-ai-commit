# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Git AI Commit is an Oh My Zsh plugin that generates AI-powered Git commit messages. It intercepts TAB key presses during `git commit -m` commands, analyzes staged changes and repository context, then streams a commit message suggestion directly into the command line.

**Tech Stack**: Python 3.11+ (core logic) + Zsh (shell integration) + OpenAI API

## Development Commands

### Environment Setup

```bash
# Install dependencies (creates .venv automatically)
uv sync

# Install with dev dependencies
uv sync --all-extras
```

### Testing & Quality

```bash
# Run tests
uv run pytest

# Format code
uv run black src/

# Lint code
uv run ruff check src/

# Type check
uv run mypy src/
```

### Manual Testing

```bash
# Run the Python script directly (must have staged changes)
source .venv/bin/activate
python src/git_ai_commit.py
deactivate
```

## Architecture

### Two-Layer Design

1. **Python Layer** (`src/git_ai_commit.py`): Core logic
   - Analyzes git diffs and repository context
   - Builds prompts with static (cacheable) and dynamic context
   - Calls OpenAI API with streaming support
   - Outputs commit message to stdout

2. **Zsh Layer** (`git-ai-commit.plugin.zsh`): Shell integration
   - Rebinds TAB key to custom `_gcommit` widget
   - Detects `git commit -m` commands (with alias expansion)
   - Launches Python script in background with animated loading
   - Captures output and injects into command buffer
   - Handles Ctrl+C cleanup and temporary files

### Key Python Components

**GitAICommit Class** (src/git_ai_commit.py:234-1083):

- `_load_config()`: Merges default → global → project-local configs
- `detect_tech_stack()`: Identifies languages/frameworks from package files
- `analyze_branch_context()`: Extracts issue refs and branch type from name
- `get_smart_file_structure()`: Returns changed files + key project files (not entire tree)
- `analyze_diff_semantics()`: Calculates stats, detects test/doc/config changes
- `_build_static_context()`: Cacheable repo context (README, tech stack, recent commits)
- `_build_dynamic_context()`: Per-commit context (diff, change stats)
- `generate_suggestion()`: Main async entry point

**CacheManager Class** (src/git_ai_commit.py:28-151):

- File-based TTL cache in `~/.cache/git-ai-commit/`
- Invalidates on branch or HEAD SHA changes
- Used for expensive operations: file structure, README parsing, tech stack detection

**Prompt Caching Strategy**:

- System message contains static context (repo info, tech stack, recent commits) → cached by OpenAI
- User message contains dynamic context (current diff, stats) → changes per commit
- Reduces API costs and latency for repeated commits

### Zsh Plugin Flow

1. User types `git commit -m` and presses TAB
2. `_gcommit` widget checks if command matches commit pattern (git-ai-commit.plugin.zsh:83-197)
3. Expands aliases (e.g., `gcmsg` → `git commit -m`)
4. Starts animated loading indicator in background
5. Runs Python script (via `uv run` or venv activation)
6. Captures output to temp file
7. Kills loading animation
8. Injects suggestion into `BUFFER` variable
9. Calls `zle reset-prompt` to refresh display
10. Waits 5 seconds (interruptible) then clears status message

**Signal Handling**:

- Ctrl+C during generation: kills loading animation, cleans up temp files, returns control
- Trap set at git-ai-commit.plugin.zsh:125 and removed at line 146

### Configuration System

Config precedence (later overrides earlier):

1. `DEFAULT_CONFIG` loaded from config/default_config.yaml
2. `~/.config/git-ai-commit/config.yaml` or `config.yml` (global)
3. `.git-ai-commit.yaml` or `.git-ai-commit.yml` in repo root (project-specific)

Note: JSON configs (`.json`) are still supported for backward compatibility but are not documented. YAML configs take precedence when both exist.

Key config sections:

- `suggestion`: Convention (conventional/gitmoji/traditional), format (single/multi-line), line length
- `openai`: Model, temperature (ignored for gpt-5/reasoning models), max_tokens
- `context`: Token budget, commit history, smart filtering, README lines, tech detection
- `caching`: TTL, API prompt caching, local caching

### Output Protocol

Python script outputs to:

- **stdout**: Commit message (plain text, no quotes)
- **stderr**: Error messages (handled by Zsh with red display)

Zsh wraps output in double quotes when injecting into command.

## Important Patterns

### Virtual Environment Management

Plugin auto-creates `.venv` on first load (git-ai-commit.plugin.zsh:14-35). Prefers `uv sync --no-dev` if available, falls back to `python3 -m venv + pip install`.

### Async/Await Usage

All OpenAI API calls use `AsyncOpenAI` client with `async for` streaming. Main entry point wraps with `asyncio.run()` (src/git_ai_commit.py:1075).

### Terminal Control

Uses `zsh/terminfo` module for cursor positioning:

- `echoti sc/rc`: save/restore cursor
- `echoti cud 1`: move cursor down
- `echoti el`: clear line
- `echoti setaf N`: set foreground color

### Model Compatibility

Temperature is conditionally set based on model (src/git_ai_commit.py:1052-1057):

- Reasoning models (o1, o3, o4): no temperature support
- GPT-5 series: only default temperature
- Older models: configurable temperature

## Known Limitations

- Doesn't work with `git commit -am` or `git commit -a -m` (requires pre-staged changes)
- Multi-line format shows message twice due to `zle reset-prompt` limitation (only resets last line)
- TAB key rebinding affects all commands, not just git (falls back to `expand-or-complete`)

## File Locations

User configs:

- `~/.config/git-ai-commit/config.yaml` (or `.yml`) (global settings)
- `.git-ai-commit.yaml` (or `.yml`) (project-specific overrides)

Runtime data:

- `~/.cache/git-ai-commit/*.json` (local cache files)
- `.venv/` in plugin directory (virtual environment)

Plugin installation:

- `${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/git-ai-commit/`
