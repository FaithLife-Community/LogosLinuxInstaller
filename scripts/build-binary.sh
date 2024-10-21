#!/usr/bin/env bash
start_dir="$PWD"
script_dir="$(dirname "$0")"
repo_root="$(dirname "$script_dir")"
cd "$repo_root"
if ! which pyinstaller >/dev/null 2>&1 || ! which oudedetai >/dev/null; then
    # Install build deps.
    python3 -m pip install .[build]
fi
pyinstaller --clean --log-level DEBUG ou_dedetai.spec
cd "$start_dir"