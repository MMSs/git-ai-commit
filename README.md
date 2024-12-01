# Git AI Commit

An AI-powered Git commit message generator that provides intelligent suggestions based on your staged changes.

## Features

- 🤖 Uses GPT-4o to generate contextual commit messages
- 🚀 Fast, streaming suggestions
- 🎯 Supports conventional commit format
- ⚙️ Configurable for both global and project-specific settings
- 🔌 Seamless Zsh shell integration

## Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/git-ai-commit.git
cd git-ai-commit
# Run the installation script
./scripts/install.sh
# Set your OpenAI API key
export OPENAI_API_KEY='your-api-key-here'
```

## Configuration

The configuration file is located at `~/.config/git-ai-commit/config.yaml`. You can also create a project-specific configuration by adding a `.git-ai-commit.yaml` file to your project root.

```yaml
suggestion:
mode: "fast" # or "quality"
format: "single-line" # or "multi-line"
max_length: 72
convention: "conventional"
# ... (see default_config.yaml for full configuration options)
```

## Usage

1. Stage your changes:
   ```bash
   git add .
   ```

2. Use the `gcsm` alias or `git commit -m` and hit space:
   ```bash
   gcsm [space]  # AI suggestion will appear
   ```

3. Actions:
   - Press Enter to accept the suggestion
   - Press Alt+R to regenerate
   - Start typing to ignore and write your own message

## CLI Commands
```bash
# Generate a suggestion
git-ai-commit suggest
# Generate with specific mode
git-ai-commit suggest --mode quality
# Configure settings
git-ai-commit configure
```

## License

MIT License
