#!/bin/bash
#
# lazygit-generate-commit.sh
#
# Generates an AI-powered commit message for use with lazygit.
# This script is called from lazygit's custom command configuration.
#
# Usage:
#   Called automatically via lazygit when pressing Ctrl+G in the files panel
#
# Prerequisites:
#   - git-ai-commit plugin installed in Oh My Zsh
#   - OPENAI_API_KEY environment variable set
#   - Staged changes in the repository
#
# Exit codes:
#   0: Success - commit message generated and committed
#   1: Failure - generation failed or commit aborted

set -euo pipefail

# Configuration
PLUGIN_DIR="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/git-ai-commit"
TEMP_COMMIT_MSG=$(mktemp .git/COMMIT_EDITMSG.XXXXXX)

# Cleanup function for temporary files
cleanup() {
    rm -f "$TEMP_COMMIT_MSG"
}

# Register cleanup on script exit, interruption, or termination
trap cleanup EXIT INT TERM

# Generate AI commit message
# Reuse the plugin environment without syncing or inheriting another uv project.
if MSG=$("$PLUGIN_DIR/.venv/bin/python" "$PLUGIN_DIR/src/git_ai_commit.py" 2>&1); then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi

# Process the generated message only if generation succeeded
if [ $EXIT_CODE -eq 0 ] && [ -n "$MSG" ]; then
    # Write generated message to temporary file
    echo "$MSG" > "$TEMP_COMMIT_MSG"

    # Open editor for user to review/edit the message
    ${EDITOR:-nvim} "$TEMP_COMMIT_MSG"

    # Commit if the file still has content (user didn't clear it)
    if [ -s "$TEMP_COMMIT_MSG" ]; then
        git commit -F "$TEMP_COMMIT_MSG"
    else
        echo "Commit aborted: message file was cleared"
        exit 1
    fi
else
    echo "Failed to generate commit message"
    read -p "Press enter to continue..."
    exit 1
fi
