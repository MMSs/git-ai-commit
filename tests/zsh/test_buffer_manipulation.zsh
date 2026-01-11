#!/usr/bin/env zsh
# Tests for buffer manipulation in git-ai-commit plugin

# Source test helpers
source "${0:A:h}/test_helpers.zsh"

echo "=================================="
echo "Buffer Manipulation Tests"
echo "=================================="

# Helper to simulate generation mode buffer update
update_buffer_generation() {
    local original_buffer="$1"
    local suggestion="$2"

    # Remove trailing space and wrap in quotes
    echo "${original_buffer/% /} \"${suggestion}\""
}

# Helper to simulate completion mode buffer update
update_buffer_completion() {
    local buffer="$1"
    local suggestion="$2"

    # Append directly to buffer
    echo "${buffer}${suggestion}"
}

# Test: Generation mode adds quotes
test_generation_adds_quotes() {
    local original="git commit -m "
    local suggestion="feat: add feature"
    local result=$(update_buffer_generation "$original" "$suggestion")

    assert_eq 'git commit -m "feat: add feature"' "$result" "Generation mode wraps in quotes"
}

# Test: Generation mode removes trailing space
test_generation_removes_trailing_space() {
    local original="git commit -m  "  # Extra space
    local suggestion="feat: add feature"
    local result=$(update_buffer_generation "$original" "$suggestion")

    # Should only have one space before quote
    assert_eq 'git commit -m "feat: add feature"' "$result" "Generation removes trailing space"
}

# Test: Completion mode appends directly
test_completion_appends() {
    local buffer='git commit -m "feat:'
    local suggestion=" add user auth"
    local result=$(update_buffer_completion "$buffer" "$suggestion")

    assert_eq 'git commit -m "feat: add user auth' "$result" "Completion appends without closing quote"
}

# Test: Completion mode preserves existing content
test_completion_preserves_content() {
    local buffer='git commit -m "feat(auth): add'
    local suggestion=" JWT tokens"
    local result=$(update_buffer_completion "$buffer" "$suggestion")

    assert_eq 'git commit -m "feat(auth): add JWT tokens' "$result" "Completion preserves original"
}

# Test: Multiple completions can be chained
test_multiple_completions() {
    local buffer='git commit -m "feat:'
    buffer=$(update_buffer_completion "$buffer" " add")
    buffer=$(update_buffer_completion "$buffer" " login")
    buffer=$(update_buffer_completion "$buffer" " feature")

    assert_eq 'git commit -m "feat: add login feature' "$buffer" "Multiple completions chain correctly"
}

# Test: Generation with --message flag
test_generation_with_message_flag() {
    local original="git commit --message "
    local suggestion="fix: resolve bug"
    local result=$(update_buffer_generation "$original" "$suggestion")

    assert_eq 'git commit --message "fix: resolve bug"' "$result" "--message flag handled"
}

# Test: Generation with other flags
test_generation_with_other_flags() {
    local original="git commit -a -m "
    local suggestion="feat: add feature"
    local result=$(update_buffer_generation "$original" "$suggestion")

    assert_eq 'git commit -a -m "feat: add feature"' "$result" "Other flags preserved"
}

# Test: Empty suggestion in generation mode
test_generation_empty_suggestion() {
    local original="git commit -m "
    local suggestion=""
    local result=$(update_buffer_generation "$original" "$suggestion")

    assert_eq 'git commit -m ""' "$result" "Empty suggestion creates empty quotes"
}

# Test: Completion with empty suggestion
test_completion_empty_suggestion() {
    local buffer='git commit -m "feat:'
    local suggestion=""
    local result=$(update_buffer_completion "$buffer" "$suggestion")

    assert_eq 'git commit -m "feat:' "$result" "Empty completion leaves buffer unchanged"
}

# Test: Suggestion with newlines (multi-line)
test_multiline_suggestion() {
    local original="git commit -m "
    local suggestion=$'feat: add feature\n\nThis adds a new feature.\n\nFixes #123'
    local result=$(update_buffer_generation "$original" "$suggestion")

    # Newlines should be preserved in the output
    assert_contains "feat: add feature" "$result" "Multiline suggestion preserved"
    assert_contains "Fixes #123" "$result" "Footer preserved in multiline"
}

# Run all tests
test_generation_adds_quotes
test_generation_removes_trailing_space
test_completion_appends
test_completion_preserves_content
test_multiple_completions
test_generation_with_message_flag
test_generation_with_other_flags
test_generation_empty_suggestion
test_completion_empty_suggestion
test_multiline_suggestion

print_summary
exit $?
