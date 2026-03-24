#!/bin/bash

set -e

SRC_PATH="/app/src/"

if [ -n "$1" ]; then
  SRC_PATH="$1"
fi

cleanup() {
    echo ""
    echo "========================================="
    echo "CODE QUALITY CHECKS FAILED"
    echo "========================================="
    echo "One or more linting checks failed - please fix the issues above"
    exit 1
}

trap cleanup ERR

echo "========================================="
echo "Running Code Quality Checks..."
echo "Target path: $SRC_PATH"
echo "========================================="

echo "Running Ruff format check..."
python -m ruff format "$SRC_PATH"
echo "Ruff format passed"
echo ""

echo "Running Ruff lint check..."
python -m ruff check "$SRC_PATH"
echo "Ruff lint passed"
echo ""

echo "Running Pyright type check..."
cd "$SRC_PATH" && python -m pyright . && cd - > /dev/null
echo "Pyright passed"
echo ""

echo "Running Flake8 check..."
python -m flake8 --config /app/src/.flake8 "$SRC_PATH"
echo "Flake8 passed"
echo ""

echo "Running Isort check..."
python -m isort "$SRC_PATH" --check-only --diff
echo "Isort passed"
echo ""

echo "========================================="
echo "ALL CHECKS PASSED"
echo "========================================="
