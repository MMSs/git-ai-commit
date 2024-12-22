#!/bin/bash

# Check if Oh My Zsh is installed
if [ ! -d "$HOME/.oh-my-zsh" ]; then
    echo "Oh My Zsh is not installed. Please install it first."
    exit 1
fi

# Get the absolute path of the plugin directory
PLUGIN_SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_TARGET_DIR="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/git-ai-commit"

# Remove existing plugin directory or symlink
if [ -e "$PLUGIN_TARGET_DIR" ]; then
    rm -rf "$PLUGIN_TARGET_DIR"
fi

# Create symlink to the plugin directory
ln -s "$PLUGIN_SOURCE_DIR" "$PLUGIN_TARGET_DIR"

# Make the python script executable
chmod +x "$PLUGIN_SOURCE_DIR/git_ai_commit.py"

echo "Plugin installed successfully!"
echo "Please add 'git-ai-commit' to your plugins array in ~/.zshrc"
echo "And set your OPENAI_API_KEY in your environment"