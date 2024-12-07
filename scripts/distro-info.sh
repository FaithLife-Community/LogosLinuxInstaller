#!/bin/sh
# Creates a text file at ~/distro-info.log with output from python's distro
# module and from various known text files that give distro details. This is
# is intended to cover as many Linux distributions as possible.

# Initialize log file.
logfile=~/distro-info.log
date --utc > "$logfile"
echo >> "$logfile"

# Determine python executable.
python=python
if which python3 >/dev/null; then
    python=python3
fi

# Record python's distro output.
if which $python >/dev/null && $python -c 'import distro' 2>/dev/null; then
    $python -c 'import distro; print(f"{distro.info()=}")' >> "$logfile"
    $python -c 'import distro; print(f"{distro.os_release_info()=}")' >> "$logfile"
    $python -c 'import distro; print(f"{distro.lsb_release_info()=}")' >> "$logfile"
    $python -c 'import distro; print(f"{distro.distro_release_info()=}")' >> "$logfile"
    $python -c 'import distro; print(f"{distro.uname_info()=}")' >> "$logfile"
    echo >> "$logfile"
fi

# As a fallback, gather [mostly] the same info that python.distro gathers.
# Ref: https://distro.readthedocs.io/en/latest/#data-sources
if [ -r /etc/os-release ]; then
    echo /etc/os-release >> "$logfile"
    cat /etc/os-release >> "$logfile"
    echo >> "$logfile"
elif [ -r /usr/lib/os-release ]; then
    echo /usr/lib/os-release >> "$logfile"
    cat /usr/lib/os-release >> "$logfile"
    echo >> "$logfile"
fi

if which lsb_release >/dev/null 2>&1; then
    echo "lsb_release -a" >> "$logfile"
    lsb_release -a >> "$logfile"
    echo >> "$logfile"
fi

if which uname >/dev/null; then
    echo "uname -rs" >> "$logfile"
    uname -rs >> "$logfile"
    echo >> "$logfile"
fi
