#!/usr/bin/env bash
start_dir="$PWD"
script_dir="$(dirname "$0")"
repo_root="$(dirname "$script_dir")"
cd "$repo_root"
if ! python -c 'import coverage' >/dev/null 2>&1; then
    echo "Error: Need to install coverage; e.g. 'pip install coverage'"
    exit 1
fi
if ! which pyinstaller >/dev/null 2>&1 || ! which oudedetai >/dev/null; then
    # Install build deps.
    python3 -m pip install .[build]
fi
if ! python -m coverage run -m unittest -b; then
    echo "Error: Must pass unittests before building"
    echo "Run 'python -m coverage run -m unittest -b -v' to see which test is failing"
    exit 1
fi
pyinstaller --clean --log-level DEBUG ou_dedetai.spec
cd "$start_dir"
