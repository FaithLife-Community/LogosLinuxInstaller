#!/usr/bin/env bash
set -e
start_dir="$PWD"
script_dir="$(dirname "$0")"
repo_root="$(dirname "$script_dir")"
cd "$repo_root"
if ! which pyinstaller >/dev/null 2>&1 || ! which oudedetai >/dev/null; then
    # Install build deps.
    python3 -m pip install .[build]
fi
# Ensure the source in our python venv is up to date
python3 -m pip install .
# Build the installer binary
pyinstaller --clean --log-level DEBUG ou_dedetai.spec
cd "$start_dir"