#!/usr/bin/env zsh
# Tests for output sanitization in git-ai-commit plugin

# Source test helpers
source "${0:A:h}/test_helpers.zsh"

echo "=================================="
echo "Sanitization Tests"
echo "=================================="

# Helper function to sanitize suggestion (mirrors plugin logic)
sanitize_suggestion() {
    local suggestion="$1"

    # Must escape backslash first, then other special characters
    suggestion="${suggestion//\\/\\\\}"     # Backslash: \ → \\
    suggestion="${suggestion//\"/\\\"}"     # Double quote: " → \"
    suggestion="${suggestion//\$/\\\$}"     # Dollar sign: $ → \$
    suggestion="${suggestion//\`/\\\`}"     # Backtick: ` → \`

    echo "$suggestion"
}

# Test: Plain text passes through unchanged
test_plain_text() {
    local input="feat: add user authentication"
    local output=$(sanitize_suggestion "$input")

    assert_eq "$input" "$output" "Plain text unchanged"
}

# Test: Backslash is escaped
test_backslash_escape() {
    local input='fix: handle \n in strings'
    local expected='fix: handle \\n in strings'
    local output=$(sanitize_suggestion "$input")

    assert_eq "$expected" "$output" "Backslash is escaped"
}

# Test: Double quote is escaped
test_double_quote_escape() {
    local input='feat: add "quoted" string'
    local expected='feat: add \"quoted\" string'
    local output=$(sanitize_suggestion "$input")

    assert_eq "$expected" "$output" "Double quote is escaped"
}

# Test: Dollar sign is escaped
test_dollar_sign_escape() {
    local input='fix: handle $variable expansion'
    local expected='fix: handle \$variable expansion'
    local output=$(sanitize_suggestion "$input")

    assert_eq "$expected" "$output" "Dollar sign is escaped"
}

# Test: Backtick is escaped
test_backtick_escape() {
    local input='feat: add `code` blocks'
    local expected='feat: add \`code\` blocks'
    local output=$(sanitize_suggestion "$input")

    assert_eq "$expected" "$output" "Backtick is escaped"
}

# Test: Multiple special chars in one string
test_multiple_special_chars() {
    local input='fix: handle "$VAR" and `cmd`'
    local expected='fix: handle \"\$VAR\" and \`cmd\`'
    local output=$(sanitize_suggestion "$input")

    assert_eq "$expected" "$output" "Multiple special chars escaped"
}

# Test: Backslash before quote (order matters)
test_backslash_before_quote() {
    local input='fix: escape \"'
    # First backslash becomes \\, then the quote becomes \"
    # So \" becomes \\\"
    local expected='fix: escape \\\"'
    local output=$(sanitize_suggestion "$input")

    assert_eq "$expected" "$output" "Backslash before quote handled correctly"
}

# Test: Command injection attempt is neutralized
test_command_injection() {
    local input='feat: $(rm -rf /)'
    local expected='feat: \$(rm -rf /)'
    local output=$(sanitize_suggestion "$input")

    assert_eq "$expected" "$output" "Command injection neutralized"
}

# Test: Backtick command injection neutralized
test_backtick_injection() {
    local input='feat: `rm -rf /`'
    local expected='feat: \`rm -rf /\`'
    local output=$(sanitize_suggestion "$input")

    assert_eq "$expected" "$output" "Backtick injection neutralized"
}

# Test: Complex real-world scenario
test_complex_scenario() {
    local input='feat(api): add endpoint for "$USER" profile with `id`'
    local expected='feat(api): add endpoint for \"\$USER\" profile with \`id\`'
    local output=$(sanitize_suggestion "$input")

    assert_eq "$expected" "$output" "Complex real-world scenario"
}

# Test: Empty string
test_empty_string() {
    local input=""
    local output=$(sanitize_suggestion "$input")

    assert_empty "$output" "Empty string stays empty"
}

# Test: Only special characters
test_only_special_chars() {
    local input='$`"\'
    # Order: \ first (but none here), then " then $ then `
    # " → \"
    # $ → \$
    # ` → \`
    # \ → \\
    local expected='\$\`\\\"'
    # Wait, let me trace through:
    # Input: $`"\
    # Step 1 (backslash): $`"\\
    # Step 2 (quote): $`\\\"
    # Step 3 (dollar): \$`\\\"
    # Step 4 (backtick): \$\`\\\"
    local output=$(sanitize_suggestion "$input")

    assert_eq '\$\`\\\"' "$output" "Only special chars handled"
}

# Test: Unicode preserved
test_unicode_preserved() {
    local input='feat: add emoji support'
    local output=$(sanitize_suggestion "$input")

    assert_eq "$input" "$output" "Unicode preserved"
}

# Run all tests
test_plain_text
test_backslash_escape
test_double_quote_escape
test_dollar_sign_escape
test_backtick_escape
test_multiple_special_chars
test_backslash_before_quote
test_command_injection
test_backtick_injection
test_complex_scenario
test_empty_string
test_only_special_chars
test_unicode_preserved

print_summary
exit $?
