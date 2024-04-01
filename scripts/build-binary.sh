#!/usr/bin/env bash
script_dir="$(dirname "$0")"
repo_root="$(dirname "$script_dir")"
if ! python -c 'import coverage' >/dev/null 2>&1; then
    echo "Error: Need to install coverage; e.g. 'pip install coverage'"
    exit 1
fi
if ! python -c 'import PyInstaller' >/dev/null 2>&1; then
    echo "Error: Need to install pyinstaller; e.g. 'pip install pyinstaller'"
    exit 1
fi
if ! python -m coverage run -m unittest -b; then
    echo "Error: Must past unittests before building"
    echo "Run 'python -m coverage run -m unittest -b -v' to see which test is failing"
    exit 1
fi
python -m PyInstaller --clean "${repo_root}/LogosLinuxInstaller.spec"
