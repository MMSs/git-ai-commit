# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Git AI Commit is an Oh My Zsh plugin that generates AI-powered Git commit messages. It intercepts TAB key presses during `git commit -m` commands, analyzes staged changes and repository context, then inserts a commit message suggestion into the command line.

**Tech Stack**: Python 3.11+ (core logic) + Zsh (shell integration) + OpenAI API or a local AI CLI

## Development Commands

### Environment Setup

```bash
# Install dependencies (creates .venv automatically)
uv sync --extra dev

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
   - Sends the prompts to a backend: the OpenAI API (non-streaming Chat Completions) or a user-configured local CLI
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

**Backends** (src/git_ai_commit_backends.py):

- `resolve_backend()`: `--backend` > `GIT_AI_COMMIT_BACKEND` > project > global > `api`
- `ApiBackend`: OpenAI Chat Completions; the only place `OPENAI_API_KEY` is required
- `CommandBackend`: runs `command.argv` without a shell in an empty temp dir, own process group; `{prompt}`, `{system_prompt}`, `{output_file}` placeholders, stdin/stdout by default; kills the group on timeout, Ctrl+C or SIGTERM
- `normalize_legacy_config()`: maps a top-level `openai:` block to `api:` per config file
- `clean_output()`: strips preamble lines, code fences and wrapping quotes for both backends

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
2. `_gcommit` widget checks cursor position and quote state (git-ai-commit.plugin.zsh:104-147)
3. Expands aliases (e.g., `gcmsg` → `git commit -m`)
4. Detects mode: generation (no quotes) or completion (unclosed quote)
5. Exports environment variables: `GIT_AI_COMMIT_MODE` and `GIT_AI_COMMIT_PARTIAL_TEXT`
6. Starts animated loading indicator in background
7. Runs Python script directly with the plugin's `.venv/bin/python`
8. Captures output to temp file
9. Kills loading animation
10. Cleans up environment variables
11. Injects suggestion into `BUFFER` variable (generation: wraps in quotes, completion: appends)
12. Calls `zle reset-prompt` to refresh display
13. Waits 5 seconds (interruptible) then clears status message

**Signal Handling**:

- Ctrl+C during generation: kills loading animation, cleans up temp files, returns control
- Trap set at git-ai-commit.plugin.zsh:182 and removed at line 212

### Two-Mode System

The plugin supports two distinct operation modes:

#### Generation Mode (Default)

**Trigger**: `git commit -m <TAB>` (no quotes)

**Behavior**:
- AI generates complete commit message from scratch
- Uses configured convention (conventional/gitmoji/traditional)
- Wraps result in double quotes
- Static context caching for optimal performance

**Example**:
```bash
git commit -m <TAB>
→ git commit -m "feat: add user authentication with JWT tokens"
```

#### Completion Mode (New)

**Trigger**: `git commit -m "partial text<TAB>` (unclosed quote)

**Behavior**:
- AI continues from user's partial text
- Matches user's style EXACTLY (ignores configured convention)
- Appends to buffer without closing quote
- Supports multiple TAB presses for iterative completion

**Example**:
```bash
git commit -m "feat(auth): this introduces <TAB>
→ git commit -m "feat(auth): this introduces secure JWT-based authentication
<TAB>
→ git commit -m "feat(auth): this introduces secure JWT-based authentication with refresh tokens
"  # User closes quote manually
```

**Technical Implementation**:

1. **Quote Detection** (Zsh layer, lines 120-144):
   - Cursor position check: only trigger at end of line
   - Extract text after `-m` or `--message` flag
   - Regex: `^\"([^\"]*)$` matches unclosed quote
   - Sets `mode` and `partial_text` variables

2. **Environment Variables**:
   - `GIT_AI_COMMIT_MODE`: "generation" or "completion"
   - `GIT_AI_COMMIT_PARTIAL_TEXT`: extracted text (completion mode only)
   - Exported before Python invocation (line 185-188)
   - Cleaned up after completion (line 220-221)

3. **Python Mode Detection** (src/git_ai_commit.py:187-190):
   - Reads environment variables in `__init__`
   - Branches in `generate_suggestion()` (line 1079)
   - Completion mode calls `_build_completion_prompt()`

4. **Completion Prompts** (src/git_ai_commit.py:935-982):
   - System prompt: Instructions to match user's style
   - User prompt: Shows partial text + diff + change stats
   - Critical instruction: Return ONLY continuation (not full message)
   - Handles spacing edge cases (partial text ends with/without space)

5. **Buffer Injection** (Zsh layer, lines 228-236):
   - Generation mode: `BUFFER="${original_buffer/% /} \"${suggestion}\""`
   - Completion mode: `BUFFER="${BUFFER}${suggestion}"`
   - Different success messages: "generated" vs "continued"

**Key Differences**:

| Aspect | Generation Mode | Completion Mode |
|--------|----------------|-----------------|
| Trigger | `git commit -m ` | `git commit -m "text` |
| Convention | Uses configured | Matches user's style |
| Output | Complete message | Continuation only |
| Quotes | Adds quotes | Leaves open |
| Caching | Static context cached | No caching benefit |
| Multiple TABs | New generation | Iterative extension |

### Configuration System

Config precedence (later overrides earlier):

1. `DEFAULT_CONFIG` loaded from config/default_config.yaml
2. `~/.config/git-ai-commit/config.yaml` or `config.yml` (global)
3. `.git-ai-commit.yaml` or `.git-ai-commit.yml` in repo root (project-specific)

Note: JSON configs (`.json`) are still supported for backward compatibility but are not documented. YAML configs take precedence when both exist.

Key config sections:

- `suggestion`: Convention (conventional/gitmoji/traditional), format (single/multi-line), line length
- `backend`: `api` (default) or `command`
- `api`: `provider` (only `openai`), model (default `gpt-6-luna`), automatically normalized `reasoning_effort`, temperature, max_tokens. Legacy top-level `openai:` is read as `api:`
- `command`: `argv` and `timeout_seconds` (default 60)
- `context`: Token budget, commit history, smart filtering, README lines, tech detection
- `caching`: TTL, API prompt caching, local caching

### Output Protocol

Python script outputs to:

- **stdout**: Commit message (plain text, no quotes)
- **stderr**: Error messages (handled by Zsh with red display)

Zsh wraps output in double quotes when injecting into command.

## Important Patterns

### Virtual Environment Management

`_git_ai_commit_ensure_venv` creates or refreshes the plugin's `.venv` when the checksum of `uv.lock` and `pyproject.toml` changes. A ready marker skips installation and Python probes on warm startup. uv uses `--locked` and an explicit plugin environment path; pip uses that environment's interpreter. Failed attempts are cached for 24 hours, then retried on the next shell startup; runnable existing environments remain available. Explicit `--retry` retries sooner and tells the user to reload the plugin afterward to bind TAB. Generation and lazygit use `.venv/bin/python` directly without syncing; lazygit reports a missing environment with a setup command.

### Async/Await Usage

OpenAI requests use `AsyncOpenAI` with non-streaming Chat Completions. Main entry point wraps with `asyncio.run()`.

### Terminal Control

Uses `zsh/terminfo` module for cursor positioning:

- `echoti sc/rc`: save/restore cursor
- `echoti cud 1`: move cursor down
- `echoti el`: clear line
- `echoti setaf N`: set foreground color

### Model Compatibility

`src/git_ai_commit_models.py` builds parameters shared by generation and completion:

- Default: `gpt-6-luna` with `reasoning_effort: none`.
- Recommended alternatives: `gpt-6.1-sol`, `gpt-6-astra`, `gpt-5.4-mini`.
- Supported effort is preserved; unsupported `none`/`minimal` maps to the lowest compatible reasoning level, and excessive effort is capped.
- GPT-5.1+ and GPT-6 send temperature only at effective effort `none`; original GPT-5 and o-series omit it.
- Positive integer `max_tokens` (including numeric strings) becomes `max_completion_tokens`, including reasoning tokens; invalid values report a configuration error.
- Null, empty, false, or missing effort omits the parameter; explicit `none` still translates per model. Unknown models and `o1-mini` omit both effort and temperature.
- Listed model aliases and dated snapshots are recognized; unlisted variants pass through with conservative API defaults. This workflow uses Chat Completions without tools.
- Dependency requirements live in `pyproject.toml`; setup fingerprints the entire dependency declaration instead of hard-coding an SDK version.
- Wheel packaging exposes the three top-level modules (git_ai_commit, git_ai_commit_models, git_ai_commit_backends) used by the console entry point and includes `git_ai_commit_data/default_config.yaml`. Direct source execution still loads `config/default_config.yaml`.

See README.md for the supported-model table and official documentation links.

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
