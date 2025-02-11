#!/usr/bin/env bash

python_ver=$(wget -qO- https://www.python.org/ftp/python/ | grep -oE '3\.12\.[0-9]+' | sort -u | tail -n1)
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
echo "e.g. Debian 12 requires:"
echo "build-essential gdb lcov pkg-config libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev liblzma-dev libncurses5-dev libreadline6-dev libsqlite3-dev libssl-dev lzma lzma-dev tk-dev uuid-dev zlib1g-dev wget"
read -r -p "Continue? [Y/n] " ans
if [[ ${ans,,} != 'y' && $ans != '' ]]; then
    exit 1
fi

# Switch into a temporary directory
TEMP_DIR=`mktemp -d`
cd $TEMP_DIR

# Download and build python3.12 from source.
echo "Downloading $python_src…"
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
echo "Installing…"
./configure --enable-shared --prefix="$prefix"
make
sudo make install

# Check install.
if [[ ! -x "$python_exec_path" ]]; then
    echo "Error: Executable not found: $python_exec_path"
    cd ~
    exit 1
fi
echo "Python $python_ver has been installed into $prefix"
if [[ "$prefix" == '/opt' ]]; then
    echo "Warning: '$prefix' is not in PATH by default."
    echo "Running Python $python_ver directly requires LD_LIBRARY_PATH:"
    echo "LD_LIBRARY_PATH=${prefix}/lib $python_exec_path"
fi
cd ~
# This fails to remove some __pycache__ files that sudo make install generated.
# No worries, they'll be removed next system reboot (as it's a temp folder)
rm -rf $TEMP_DIR 2> /dev/null
