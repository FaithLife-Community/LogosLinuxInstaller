#!/usr/bin/env bash

python_ver='3.12.1'
prefix=/opt
venv=./env

# Derived vars.
python_exec_ver="${python_ver%.*}"
python_exec_path="${prefix}/bin/python${python_exec_ver}"

# Check parent dir.
if [[ ! $(basename "$PWD") == 'LogosLinuxInstaller' ]]; then
    echo "Error: PWD needs to be './LogosLinuxInstaller'"
    echo "LogosLinuxInstaller can be cloned from https://github.com/FaithLife-Community/LogosLinuxInstaller.git"
    exit 1
fi

# Check for git repo.
if ! git status >/dev/null 2>&1; then
    echo "Error: $PWD is not a git repo"
    exit 1
fi

# Check for existing venv.
if [[ -d "$venv" ]]; then
    echo "Error: Folder already exists: $venv"
    exit 1
fi

# Initialize venv.
"$python_exec_path" -m venv "$venv"
echo "LD_LIBRARY_PATH=${prefix}/lib" >> "${venv}/bin/activate"
echo 'export LD_LIBRARY_PATH' >> "${venv}/bin/activate"
echo "Virtual env setup as '${venv}/'. Activate with:"
echo "source ${venv}/bin/activate"
echo
echo "Install runtime dependencies with:"
echo "pip install -r requirements.txt"
echo
echo "To build locally install pyinstaller with:"
echo "pip install pyinstaller"
