#!/usr/bin/env zsh
# Test helper functions for Zsh plugin tests

# Color codes for test output
typeset -g RED='\033[0;31m'
typeset -g GREEN='\033[0;32m'
typeset -g YELLOW='\033[0;33m'
typeset -g NC='\033[0m' # No Color

# Test counters
typeset -g TESTS_RUN=0
typeset -g TESTS_PASSED=0
typeset -g TESTS_FAILED=0

# Assert equality
# Usage: assert_eq "expected" "actual" "test description"
assert_eq() {
    local expected="$1"
    local actual="$2"
    local description="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [[ "$expected" == "$actual" ]]; then
        echo -e "${GREEN}PASS${NC}: $description"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}: $description"
        echo "  Expected: '$expected'"
        echo "  Actual:   '$actual'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Assert not equal
# Usage: assert_ne "not_expected" "actual" "test description"
assert_ne() {
    local not_expected="$1"
    local actual="$2"
    local description="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [[ "$not_expected" != "$actual" ]]; then
        echo -e "${GREEN}PASS${NC}: $description"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}: $description"
        echo "  Should not be: '$not_expected'"
        echo "  But was:       '$actual'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Assert string contains
# Usage: assert_contains "substring" "string" "test description"
assert_contains() {
    local substring="$1"
    local string="$2"
    local description="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [[ "$string" == *"$substring"* ]]; then
        echo -e "${GREEN}PASS${NC}: $description"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}: $description"
        echo "  String: '$string'"
        echo "  Should contain: '$substring'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Assert empty
# Usage: assert_empty "$var" "test description"
assert_empty() {
    local value="$1"
    local description="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [[ -z "$value" ]]; then
        echo -e "${GREEN}PASS${NC}: $description"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}: $description"
        echo "  Expected empty, got: '$value'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Assert not empty
# Usage: assert_not_empty "$var" "test description"
assert_not_empty() {
    local value="$1"
    local description="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [[ -n "$value" ]]; then
        echo -e "${GREEN}PASS${NC}: $description"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}: $description"
        echo "  Expected non-empty value"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Print test summary
print_summary() {
    echo ""
    echo "=================================="
    echo "Test Summary"
    echo "=================================="
    echo "Total:  $TESTS_RUN"
    echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Failed: ${RED}$TESTS_FAILED${NC}"

    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "\n${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "\n${RED}Some tests failed!${NC}"
        return 1
    fi
}

# Reset test counters
reset_counters() {
    TESTS_RUN=0
    TESTS_PASSED=0
    TESTS_FAILED=0
}
