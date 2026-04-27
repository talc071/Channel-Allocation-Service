#!/usr/bin/env bash
# One-command test runner for macOS / Linux.
# Creates a venv if missing, installs deps, then runs pytest.
# Usage:  bash run_tests.sh

set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

echo "Installing dependencies..."
.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt

echo "Running tests..."
.venv/bin/python -m pytest
