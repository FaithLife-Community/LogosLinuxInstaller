#!/usr/bin/env bash

python_ver='3.12.1'
prefix=/opt

# Derived vars.
srcdir="Python-${python_ver}"
tarxz="${srcdir}.tar.xz"
python_src="https://www.python.org/ftp/python/${python_ver}/${tarxz}"
python_exec_ver="${python_ver%.*}"
python_exec_path="${prefix}/bin/python${python_exec_ver}"


if [[ $(which "python${python_exec_ver}") || -x "$python_exec_path" ]]; then
    echo "Python-${python_ver} is already installed!"
    exit 0
fi

# Warn about build deps.
echo "Warning: You will likely need to install build dependencies for your system."
echo "e.g. Ubuntu requires: build-essential libreadline-dev libsqlite3-dev tk-dev tcl-dev"
read -r -p "Continue? [y/N]: " ans
if [[ ${ans,,} != 'y' ]]; then
    exit 1
fi

# Download and build python3.12 from source.
echo "Downloading $python_src..."
wget "$python_src"
if [[ -r "$tarxz" ]]; then
    tar xf "$tarxz"
else
    echo "Error: Downloaded file not found: $tarxz"
    exit 1
fi

# Enter src code dir.
if [[ -d "$srcdir" ]]; then
    # shellcheck disable=SC2164
    cd "Python-${python_ver}"
else
    echo "Error: Folder not found: $srcdir"
    exit 1
fi

# Install python.
echo "Installing..."
./configure \
    --enable-shared \
    --enable-loadable-sqlite-extensions \
    --prefix="$prefix"
make
sudo make install

# Check install.
if [[ ! -x "$python_exec_path" ]]; then
    echo "Error: Executable not found: $python_exec_path"
    exit 1
fi
echo "Python $python_ver has been installed into $prefix"
if [[ "$prefix" == '/opt' ]]; then
    echo "Warning: '$prefix' is not in PATH by default."
    echo "Running Python $python_ver directly requires LD_LIBRARY_PATH:"
    echo "LD_LIBRARY_PATH=${prefix}/lib $python_exec_path"
fi
