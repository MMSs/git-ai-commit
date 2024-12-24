# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3 first."
    return 1
fi

# Plugin directory
PLUGIN_DIR="${0:A:h}"

# Function to ensure virtualenv is set up
_git_ai_commit_ensure_venv() {
    local venv_dir="${PLUGIN_DIR}/.venv"

    # Create virtualenv if it doesn't exist
    if [[ ! -d "$venv_dir" ]]; then
        echo "Setting up git-ai-commit environment..."
        python3 -m venv "$venv_dir"
        source "$venv_dir/bin/activate"
        pip install openai
        deactivate
    fi
}

# Initialize the plugin
_git_ai_commit_ensure_venv

# Function to handle git commit message generation
_gcommit() {
    local cmd=$BUFFER
    # Check if the command is an alias and expand it
    if a=$(alias ${BUFFER%% *} 2>/dev/null); then
        cmd=${a#*=}
        cmd=${cmd//\'/}
        cmd=${cmd//\"/}
        cmd="$cmd "
    fi

    # Check if the command is a git commit with -m/--message flag
    if [[ $cmd =~ ^git\ commit.*(-m|--message)\  && $BUFFER =~ ^[^\"]*$ ]]; then
        # Handle autosuggestions
        if zle -l | grep -q autosuggest-disable; then
            zle autosuggest-disable
        fi

        # Save current buffer
        local original_buffer=$BUFFER

        # Generate commit message with streaming output
        local venv_dir="${PLUGIN_DIR}/.venv"
        source "$venv_dir/bin/activate"

        # Create a temporary file to store the final message
        local temp_file=$(mktemp)

        # Run Python script and show streaming output while capturing message
        python3 "${PLUGIN_DIR}/src/git_ai_commit.py" | tee "$temp_file"
        local exit_status=$?
        local suggestion=$(cat "$temp_file")
        rm "$temp_file"

        deactivate

        # If we got a suggestion, update the command line
        if [[ $exit_status -eq 0 && -n "$suggestion" ]]; then
            # surround the suggestion with quotes
            suggestion=" \"$suggestion\""
            # Restore the original command and add the suggestion
            zle reset-prompt
            BUFFER="${original_buffer%% }$suggestion"
            CURSOR=${#BUFFER}
        else
            echo "Failed to generate commit message"
            BUFFER=$original_buffer
        fi

        # Re-enable autosuggestions if necessary
        if zle -l | grep -q autosuggest-enable; then
            zle autosuggest-enable
        fi
    else
        zle expand-or-complete
    fi
}

# Register the widget and bind the key
zle -N _gcommit
bindkey "^I" _gcommit
