# Check if Python is installed
if ! command -v python3 &>/dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3 first."
    return 1
fi

# Load terminfo module for terminal control
zmodload zsh/terminfo

# Use terminfo for terminal control (zsh-specific, more robust than ANSI codes)
# The terminfo module provides portable terminal capabilities through the system's terminfo database:
#   - echoti sc/rc: save and restore cursor position
#   - echoti cud/cuu: move cursor down/up
#   - echoti setaf: set foreground color by capability, not hardcoded ANSI codes
#   - echoti el: clear to end of line
# This approach is more robust than raw ANSI escape codes because it queries the terminal's
# actual capabilities, ensuring compatibility across different terminal emulators.
# Note: Git hooks use ANSI codes instead since they run in bash, not zsh.

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
                _git_ai_commit_display_message "${base_msg}${dots}" $color
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
    # Only trigger if cursor is at end of line
    if [[ $CURSOR -ne ${#BUFFER} ]]; then
        zle expand-or-complete
        return
    fi

    local cmd=$BUFFER
    # Check if the command is an alias and expand it
    if a=$(alias ${BUFFER%% *} 2>/dev/null); then
        local expanded_alias=${a#*=}
        expanded_alias=${expanded_alias//\'/}
        expanded_alias=${expanded_alias//\"/}
        # Check if there are arguments after the alias
        if [[ $BUFFER == *" "* ]]; then
            local rest_of_cmd="${BUFFER#* }"
            cmd="$expanded_alias $rest_of_cmd"
        else
            cmd="$expanded_alias"
        fi
    fi

    # Handle git push: append current branch name when cursor sits after
    # `(-u|--set-upstream|--no-set-upstream) <valid-remote>` (with optional trailing space).
    if [[ $cmd =~ ^git[[:space:]]+push[[:space:]] ]]; then
        if [[ $cmd =~ (^|[[:space:]])(-u|--set-upstream|--no-set-upstream)[[:space:]]+([^[:space:]]+)[[:space:]]*$ ]]; then
            local push_remote="${match[3]}"
            if git remote 2>/dev/null | grep -qx -- "$push_remote"; then
                local push_branch
                push_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
                if [[ -n "$push_branch" && "$push_branch" != "HEAD" ]]; then
                    BUFFER="${BUFFER/% /} ${push_branch}"
                    CURSOR=${#BUFFER}
                    _git_ai_commit_ensure_status_line
                    _git_ai_commit_display_message "✓ Branch: ${push_branch}" 2
                    zle reset-prompt
                    local user_key
                    if read -t 3 -k 1 user_key 2>/dev/null; then
                        if [[ $user_key == [[:print:]] ]]; then
                            BUFFER="${BUFFER}${user_key}"
                            CURSOR=${#BUFFER}
                        fi
                    fi
                    zle reset-prompt
                    return
                fi
            fi
        fi
    fi

    # Quote state detection for two-mode system:
    # - Generation mode: git commit -m (no quotes)
    # - Completion mode: git commit -m "partial text (unclosed quote)
    local mode=""
    local partial_text=""
    local after_flag=""

    # Extract portion after -m or --message flag (use .* for greedy matching to get last -m)
    if [[ $cmd =~ (-m|--message)[[:space:]]+(.*) ]]; then
        after_flag="${match[2]}"
    fi

    # Detect quote state and mode
    if [[ -z "$after_flag" ]]; then
        # No argument after -m flag → generation mode
        mode="generation"
    elif [[ $after_flag =~ ^\"([^\"]*)$ ]]; then
        # Unclosed quote → completion mode
        mode="completion"
        partial_text="${match[1]}"
    else
        # Closed quote or other pattern → don't trigger, use normal TAB
        zle expand-or-complete
        return
    fi

    # Check if this is a git commit command with -m or --message
    if [[ $cmd =~ ^git\ commit.*(-m|--message) && -n "$mode" ]]; then
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
            unset GIT_AI_COMMIT_MODE
            unset GIT_AI_COMMIT_PARTIAL_TEXT
        }

        # Generate commit message with streaming output
        local temp_file=$(mktemp)
        local error_file=$(mktemp)
        local exit_status
        local current_dir="$PWD"

        # Set up trap to catch Ctrl+C (SIGINT) and SIGTERM and clean up
        trap '_cleanup_loading; return 1' INT TERM

        # Export environment variables for Python script to detect mode and partial text
        export GIT_AI_COMMIT_MODE="$mode"
        if [[ "$mode" == "completion" ]]; then
            export GIT_AI_COMMIT_PARTIAL_TEXT="$partial_text"
        fi

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

        # Stop the loading animation
        kill $loading_pid 2>/dev/null
        wait $loading_pid 2>/dev/null

        # Remove the trap
        trap - INT TERM

        local suggestion=$(cat "$temp_file")
        local error_msg=$(cat "$error_file")
        rm "$temp_file" "$error_file"

        # Sanitize suggestion to prevent command injection
        # Escape characters that could break out of double-quoted string context
        # This is critical since suggestion is injected directly into BUFFER
        if [[ -n "$suggestion" ]]; then
            # Must escape backslash first, then other special characters
            suggestion="${suggestion//\\/\\\\}"     # Backslash: \ → \\
            suggestion="${suggestion//\"/\\\"}"     # Double quote: " → \"
            suggestion="${suggestion//\$/\\\$}"     # Dollar sign: $ → \$
            suggestion="${suggestion//\`/\\\`}"     # Backtick: ` → \`
        fi

        # Clean up environment variables
        unset GIT_AI_COMMIT_MODE
        unset GIT_AI_COMMIT_PARTIAL_TEXT

        # Clear the loading indicator
        _git_ai_commit_clear_message

        # If we got a suggestion, update the command line
        if [[ $exit_status -eq 0 && -n "$suggestion" ]]; then
            if [[ "$mode" == "completion" ]]; then
                # Completion mode: append to existing buffer, leave quote open
                BUFFER="${BUFFER}${suggestion}"
                _git_ai_commit_display_message "✓ Commit message continued" 2
            else
                # Generation mode: wrap in quotes (current behavior)
                BUFFER="${original_buffer/% /} \"${suggestion}\""
                _git_ai_commit_display_message "✓ Commit message generated" 2
            fi
            CURSOR=${#BUFFER}
            # Reset prompt to print the generated commit message
            zle reset-prompt
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

        # Wait up to 3 seconds before clearing the status message, but allow any keypress to interrupt
        # This timeout is intended to provide:
        #   - Enough time for users to see success/error messages
        #   - Quick return to normal command line interaction
        #   - Immediate interruption on any user input to resume typing
        # The -k 1 option reads a single keypress, and printable characters are added to BUFFER
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
