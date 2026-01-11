#!/usr/bin/env zsh
# Tests for mode detection logic in git-ai-commit plugin

# Source test helpers
source "${0:A:h}/test_helpers.zsh"

echo "=================================="
echo "Mode Detection Tests"
echo "=================================="

# Helper function to detect mode from a command
# This simulates the mode detection logic from the plugin
detect_mode() {
    local cmd="$1"
    local mode=""
    local partial_text=""
    local after_flag=""

    # Extract portion after -m or --message flag
    if [[ $cmd =~ (-m|--message)[[:space:]]+(.*) ]]; then
        after_flag="${match[2]}"
    fi

    # Detect quote state and mode
    if [[ -z "$after_flag" ]]; then
        mode="generation"
    elif [[ $after_flag =~ ^\"([^\"]*)$ ]]; then
        mode="completion"
        partial_text="${match[1]}"
    else
        mode="none"  # Closed quote or other pattern
    fi

    echo "$mode|$partial_text"
}

# Test: Basic git commit -m with no quotes should be generation mode
test_generation_mode_no_quotes() {
    local result=$(detect_mode "git commit -m ")
    local mode="${result%%|*}"
    local partial="${result#*|}"

    assert_eq "generation" "$mode" "git commit -m (no quotes) -> generation mode"
    assert_empty "$partial" "No partial text in generation mode"
}

# Test: git commit -m with unclosed quote should be completion mode
test_completion_mode_unclosed_quote() {
    local result=$(detect_mode 'git commit -m "feat:')
    local mode="${result%%|*}"
    local partial="${result#*|}"

    assert_eq "completion" "$mode" "git commit -m \"feat: -> completion mode"
    assert_eq "feat:" "$partial" "Partial text extracted correctly"
}

# Test: git commit -m with closed quote should not trigger
test_closed_quote_no_trigger() {
    local result=$(detect_mode 'git commit -m "complete message"')
    local mode="${result%%|*}"

    assert_eq "none" "$mode" "Closed quote should not trigger AI"
}

# Test: git commit -m with empty unclosed quote
test_empty_unclosed_quote() {
    local result=$(detect_mode 'git commit -m "')
    local mode="${result%%|*}"
    local partial="${result#*|}"

    assert_eq "completion" "$mode" "Empty unclosed quote -> completion mode"
    assert_empty "$partial" "Partial text is empty for just quote"
}

# Test: --message flag variant
test_message_flag_long_form() {
    local result=$(detect_mode 'git commit --message ')
    local mode="${result%%|*}"

    assert_eq "generation" "$mode" "--message flag triggers generation mode"
}

# Test: --message with unclosed quote
test_message_flag_with_quote() {
    local result=$(detect_mode 'git commit --message "fix:')
    local mode="${result%%|*}"
    local partial="${result#*|}"

    assert_eq "completion" "$mode" "--message with quote -> completion mode"
    assert_eq "fix:" "$partial" "Partial text from --message flag"
}

# Test: Partial text with spaces
test_partial_text_with_spaces() {
    local result=$(detect_mode 'git commit -m "feat: add user')
    local mode="${result%%|*}"
    local partial="${result#*|}"

    assert_eq "completion" "$mode" "Partial with spaces -> completion mode"
    assert_eq "feat: add user" "$partial" "Partial text with spaces preserved"
}

# Test: Command with flags before -m
test_flags_before_m() {
    local result=$(detect_mode 'git commit -a -m ')
    local mode="${result%%|*}"

    assert_eq "generation" "$mode" "git commit -a -m -> generation mode"
}

# Test: Complex partial text with special chars
test_partial_with_parens() {
    local result=$(detect_mode 'git commit -m "feat(auth):')
    local mode="${result%%|*}"
    local partial="${result#*|}"

    assert_eq "completion" "$mode" "Partial with parens -> completion mode"
    assert_eq "feat(auth):" "$partial" "Partial with scope preserved"
}

# Run all tests
test_generation_mode_no_quotes
test_completion_mode_unclosed_quote
test_closed_quote_no_trigger
test_empty_unclosed_quote
test_message_flag_long_form
test_message_flag_with_quote
test_partial_text_with_spaces
test_flags_before_m
test_partial_with_parens

print_summary
exit $?
