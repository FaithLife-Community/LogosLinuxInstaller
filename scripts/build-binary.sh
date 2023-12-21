#!/usr/bin/env bash
script_dir="$(dirname "$0")"
repo_root="$(dirname "$script_dir")"
if ! which pyinstaller; then
    echo "Error: Need to install pyinstaller; e.g. 'pip3 install pyinstaller'"
    exit 1
fi
pyinstaller --clean "${repo_root}/LogosLinuxInstaller.spec"
