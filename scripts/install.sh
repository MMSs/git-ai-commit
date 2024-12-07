#!/bin/bash

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Function to handle errors
handle_error() {
    echo -e "${RED}Error: $1${NC}"
    exit 1
}

echo "Installing git-ai-commit..."

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Poetry is not installed. Installing poetry...${NC}"
    curl -sSL https://install.python-poetry.org | python3 -

    # Inform the user to update their PATH
    echo -e "${RED}Please add the following line to your shell configuration file:${NC}"
    echo 'export PATH="$HOME/.local/bin:$PATH"'
    echo -e "${RED}Then restart your shell or run: source ~/.zshrc then run this script again.${NC}"
    exit 1
fi

# Install dependencies
poetry install || handle_error "Failed to install dependencies with Poetry."

# Create configuration directory
mkdir -p ~/.config/git-ai-commit || handle_error "Failed to create configuration directory."

# Copy default configuration
cp config/default_config.yaml ~/.config/git-ai-commit/config.yaml || handle_error "Failed to copy default configuration."

# Install shell integration
SHELL_INTEGRATION_OUTPUT=$(poetry run python -c "from src.shell_integration import ShellIntegration; print(ShellIntegration.install())" 2>&1)
if [ $? -ne 0 ]; then
    handle_error "Failed to install shell integration: $SHELL_INTEGRATION_OUTPUT"
fi

# Check if shell integration was successful
if [[ $SHELL_INTEGRATION_OUTPUT == *"already installed"* ]] || [[ $SHELL_INTEGRATION_OUTPUT == *"successfully"* ]]; then
    echo -e "${GREEN}$SHELL_INTEGRATION_OUTPUT${NC}"
    echo -e "${GREEN}Installation complete!${NC}"
    echo "Please set your OpenAI API key in ~/.config/git-ai-commit/config.yaml or as an environment variable: OPENAI_API_KEY"
    echo "Restart your shell or run: source ~/.zshrc"
else
    handle_error "Unexpected output from shell integration: $SHELL_INTEGRATION_OUTPUT"
fi