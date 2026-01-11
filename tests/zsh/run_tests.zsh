#!/usr/bin/env zsh
# Runner script for all Zsh plugin tests

set -e

SCRIPT_DIR="${0:A:h}"
TOTAL_PASSED=0
TOTAL_FAILED=0

echo "╔══════════════════════════════════════════╗"
echo "║     Git AI Commit - Zsh Plugin Tests     ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Run each test file
for test_file in "$SCRIPT_DIR"/test_*.zsh; do
    if [[ "$test_file" == *"test_helpers.zsh" ]]; then
        continue
    fi

    echo "Running: ${test_file:t}"
    echo ""

    # Run the test file and capture output
    if zsh "$test_file"; then
        echo ""
    else
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
        echo ""
    fi
done

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           Final Results                  ║"
echo "╚══════════════════════════════════════════╝"

if [[ $TOTAL_FAILED -eq 0 ]]; then
    echo -e "\033[0;32mAll test suites passed!\033[0m"
    exit 0
else
    echo -e "\033[0;31m$TOTAL_FAILED test suite(s) had failures\033[0m"
    exit 1
fi
