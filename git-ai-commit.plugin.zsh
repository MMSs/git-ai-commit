# Check if Python is installed
if ! command -v python3 &>/dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3 first."
    return 1
fi

# Load terminfo module for terminal control
zmodload zsh/terminfo

# Plugin directory
PLUGIN_DIR="${0:A:h}"

# Function to ensure virtualenv is set up
_git_ai_commit_ensure_venv() {
    local venv_dir="${PLUGIN_DIR}/.venv"

    # Create virtualenv if it doesn't exist
    if [[ ! -d "$venv_dir" ]]; then
        echo "Setting up git-ai-commit environment..."

        # Check if uv is available and prefer it
        if command -v uv &>/dev/null; then
            echo "Using uv to install dependencies..."
            cd "$PLUGIN_DIR"
            uv sync --no-dev
            cd - > /dev/null
        else
            echo "Using standard pip (consider installing uv for faster setup: https://github.com/astral-sh/uv)"
            python3 -m venv "$venv_dir"
            source "$venv_dir/bin/activate"
            pip install .
            deactivate
        fi
    fi
}

# Initialize the plugin
_git_ai_commit_ensure_venv

# Function to ensure there's a line below the prompt for status messages
# This handles the case when the prompt is at the bottom of the terminal
_git_ai_commit_ensure_status_line() {
    # Print a newline to create space (this scrolls the terminal if at bottom)
    printf '\n'
    # Move cursor back up to the original prompt line
    echoti cuu 1
}

# Function to display a message on the line below the prompt
_git_ai_commit_display_message() {
    local message=$1
    local color=${2:-3}  # Default to yellow (3)

    # Note: Assumes _git_ai_commit_ensure_status_line was called first
    # to guarantee space exists below the prompt
    echoti sc                          # save_cursor
    echoti cud 1                       # cursor_down 1 line
    echoti cr                          # carriage_return (move to start of line)
    echoti el                          # clr_eol (clear the line first)
    echoti setaf $color                # set_foreground (color)
    printf %s "$message"
    echoti sgr 0                       # exit_attribute_mode
    echoti rc                          # restore_cursor
}

# Function to animate loading dots
_git_ai_commit_loading() {
    local base_msg="🤖 Generating commit message"
    local color=3  # Yellow

    while true; do
        for i in {0..3}; do
            if [[ $i -eq 0 ]]; then
                _git_ai_commit_display_message "$base_msg" $color
            else
                local dots=$(printf '.%.0s' $(seq 1 $i))
                _git_ai_commit_display_message "${base_msg} ${dots}" $color
            fi
            sleep 0.3
        done
    done
}

# Function to clear the message area at the bottom
_git_ai_commit_clear_message() {
    echoti sc                          # save_cursor
    echoti cud 1                       # cursor_down 1 line
    echoti cr                          # carriage_return
    echoti el                          # clr_eol (clear the line)
    echoti rc                          # restore_cursor
}

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

    # Check if the command is a git commit with -m/--message flag and doesn't already have a complete message
    if [[ $cmd =~ ^git\ commit.*(-m|--message)\  && ! $BUFFER =~ \".*\" ]]; then
        # Disable autosuggestions temporarily to avoid conflicts
        if zle -l | grep -q autosuggest-disable; then
            zle autosuggest-disable
        fi

        # Save current buffer and remove any trailing space
        local original_buffer=${BUFFER}

        # Ensure there's a line below the prompt for status messages
        # This handles the case when the prompt is at the bottom of the terminal
        _git_ai_commit_ensure_status_line

        # Start animated loading indicator in background, suppressing job control messages
        setopt local_options no_notify no_monitor
        {
            _git_ai_commit_loading
        } &
        local loading_pid=$!

        # Set up cleanup function for Ctrl+C
        _cleanup_loading() {
            kill $loading_pid 2>/dev/null
            wait $loading_pid 2>/dev/null
            _git_ai_commit_clear_message
            rm -f "$temp_file" "$error_file" 2>/dev/null
        }

        # Generate commit message with streaming output
        local temp_file=$(mktemp)
        local error_file=$(mktemp)
        local exit_status
        local current_dir="$PWD"

        # Set up trap to catch Ctrl+C (SIGINT) and clean up
        trap '_cleanup_loading; return 1' INT

        # Use uv run if uv is available and venv exists, otherwise use traditional activation
        if command -v uv &>/dev/null && [[ -d "${PLUGIN_DIR}/.venv" ]]; then
            (
                uv run --project "${PLUGIN_DIR}" python "${PLUGIN_DIR}/src/git_ai_commit.py"
            ) > "$temp_file" 2> "$error_file"
            exit_status=$?
        else
            (
                source "${PLUGIN_DIR}/.venv/bin/activate" || exit 1
                cd "$current_dir" || exit 1
                python3 "${PLUGIN_DIR}/src/git_ai_commit.py"
                local result=$?
                deactivate
                exit $result
            ) > "$temp_file" 2> "$error_file"
            exit_status=$?
        fi

        # Remove the trap
        trap - INT

        # Stop the loading animation
        kill $loading_pid 2>/dev/null
        wait $loading_pid 2>/dev/null

        local suggestion=$(cat "$temp_file")
        local error_msg=$(cat "$error_file")
        rm "$temp_file" "$error_file"

        # Clear the loading indicator
        _git_ai_commit_clear_message

        # If we got a suggestion, update the command line
        if [[ $exit_status -eq 0 && -n "$suggestion" ]]; then
            BUFFER="${original_buffer/% /} \"${suggestion}\""
            CURSOR=${#BUFFER}
            # Reset prompt to print the generated commit message
            zle reset-prompt
            # Display success indicator briefly
            _git_ai_commit_display_message "✓ Commit message generated" 2
        else
            # On error, restore original buffer and display error
            BUFFER=$original_buffer
            CURSOR=${#BUFFER}

            if [[ -n "$error_msg" ]]; then
                # Strip ANSI codes and newlines from error message for display
                local clean_error=${error_msg//$'\n'/ }
                clean_error=${clean_error//[$'\033']\[*([0-9;])m/}
                _git_ai_commit_display_message "$clean_error" 1
            fi
        fi

        # Wait up to 3 seconds, but allow any keypress to interrupt
        local user_key
        if read -t 3 -k 1 user_key 2>/dev/null; then
            # Only add printable characters to the buffer
            if [[ $user_key == [[:print:]] ]]; then
                BUFFER="${BUFFER}${user_key}"
                CURSOR=${#BUFFER}
            fi
        fi
        # Then reset prompt to remove the message
        zle reset-prompt

        # Re-enable autosuggestions if available
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
