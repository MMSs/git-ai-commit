# Git AI Commit

An AI-powered Git commit message generator Oh My Zsh plugin that provides intelligent suggestions based on your staged changes, and itegrates seamlessly with your existing git workflow.

Just stage your changes and type `git commit -m` (or any alias for it) and hit TAB to generate a commit message.

## Features

- 🤖 Uses GPT-4o to generate contextual commit messages
- 🚀 Fast, streaming suggestions
- 🎯 Supports conventional commit format, gitmoji, and your own custom formats
- ⚙️ Configurable for both global and project-specific settings
- 🔌 Native Oh My Zsh integration

## Prerequisites

- [Oh My Zsh](https://ohmyz.sh/) installed
- Python 3.11 or higher
- OpenAI API key

## Installation

1. Clone this repository in Oh My Zsh's plugins directory:

```bash
git clone https://github.com/MMSs/git-ai-commit.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/git-ai-commit
```

2. Add the plugin to your Oh My Zsh configuration. Open your `.zshrc` and add `git-ai-commit` to your plugins:

```bash
plugins=(... git-ai-commit)
```

3. Set your OpenAI API key in your `.zshrc`:

```bash
export OPENAI_API_KEY='your-api-key-here'
```

4. Restart your terminal or reload Oh My Zsh:

```bash
source ~/.zshrc
```

To update the plugin, run `git -C ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/git-ai-commit pull` then restart your terminal or reload Oh My Zsh as described in step 4.

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

## Known issues

- The plugin doesn't work with `git commit -am` or `git commit -a -m`, you need to stage your changes first.
- If you're using mult-line format, you will see the message twice, this is due to limitation of zsh prompt-reset that resets only the last line of the prompt.

## License

MIT License
