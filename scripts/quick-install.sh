#!/usr/bin/env bash

# This script assumes you've managed all the system prerequisites yourself.
# It can be run non-interactively if you prepare a few things beforehand:
# 1. Set env varaibles. 
#   - LOGOS_RELEASE_VERSION (e.g. 38.1.0.0002)
#   - LOGOS_WINEPREFIX (e.g. $HOME/wine-logos)
#   - LOGOS_WINE (e.g. /opt/wine-devel/bin/wine64)
# 2. Download needed files to Downloads folder:
#   - icu-win.tar.gz
#   - Logos_v${LOGOS_RELEASE_VERSION}-x64.msi
# 3. Run using '-y' option.

if [[ $0 == ${BASH_SOURCE[0]} ]]; then
    echo "Error: This script should be sourced rather than run directly; e.g."
    echo "source $0"
    exit 1
fi

ICU_NAME='icu-win.tar.gz'
FILE="${BASH_SOURCE[0]}"
REPO="$(dirname "$(dirname "$FILE")")"

if [[ $1 == '-y' ]]; then
    ASSUME_YES=1
fi

# Set env variables.
while [[ -z $LOGOS_RELEASE_VERSION ]]; do
    read -p "Logos installer release version (##.#.#.####): " ans
    if [[ -n $ans ]]; then
        export LOGOS_RELEASE_VERSION="$ans"
    fi
done
LOGOS_MSI_NAME="Logos_v${LOGOS_RELEASE_VERSION}-x64.msi"

while [[ -z $LOGOS_WINEPREFIX ]]; do
    read -p "Full path to Logos wineprefix directory (variables will not be expanded!): " ans
    if [[ -n $ans ]]; then
        export LOGOS_WINEPREFIX="$ans"
    fi
done
mkdir -p $LOGOS_WINEPREFIX
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to create LOGOS_WINEPREFIX."
    return 1
fi
export WINEPREFIX="$LOGOS_WINEPREFIX"

while [[ -z $LOGOS_WINE ]]; do
    read -p "Full path to wine binary (variables will not be expanded!): " ans
    if [[ -n $ans ]]; then
        export LOGOS_WINE="$ans"
    fi
done
if ! "$LOGOS_WINE" --version >/dev/null 2>&1; then
    echo "Error: Can't run wine binary."
    return 1
fi
export LOGOS_WINEDIR="$(dirname $LOGOS_WINE)"
export WINE="$LOGOS_WINE"
export WINELOADER="$LOGOS_WINE"
export WINESERVER="$LOGOS_WINEDIR/wineserver"

echo -e "\nInstallation variables:"
env | grep -e WINE -e LOGOS | sort
# Get user confirmation if run interactively.
if [[ -z $ASSUME_YES ]]; then
    read -p "Proceed to installation? [Y/n]: " ans
    if [[ -n $ans && ${ans,,} != 'y' ]]; then
        return 1
    fi
fi

# Get user Downloads dir.
DOWNLOADS="$(xdg-user-dir DOWNLOAD)"

# Initialize wine.
if [[ ! -r $WINEPREFIX/system.reg ]]; then
    echo "Initializing wine."
    WINEDLLOVERRIDES='mscoree,mshtml=' $WINE wineboot --init || return 1
fi

# Configure system.
echo "Setting renderer=gdi."
$WINE reg add 'HKCU\Software\Wine\Direct3D' /v 'renderer' /d 'gdi' /f || return 1
echo "Setting winemenubuilder.exe=''."
# $WINE reg add 'HKCU\Software\Wine\DllOverrides' /v 'winemenubuilder.exe' /d '' /f || return 1
# NOTE: Using reg file here b/c the empty data string in reg add command is ignored.
tempfile=/tmp/disable-winemenubuilder.reg
cat << EOF >"$tempfile"
REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winemenubuilder.exe"=""
EOF
$WINE regedit "$tempfile" || return 1
rm -f "$tempfile"
if [[ ! -r $WINEPREFIX/drive_c/windows/globalization/ICU/icudtl.dat ]]; then
    echo "Extracting ICU files into $WINEPREFIX/drive_c/:"
    if [[ ! -r $DOWNLOADS/$ICU_NAME ]]; then
        echo "Error: Please download $ICU_NAME from https://github.com/FaithLife-Community/icu/releases"
        return 1
    fi
    tar -xvf "$DOWNLOADS/$ICU_NAME" --directory "$WINEPREFIX/drive_c"
else
    echo "ICU files already installed."
fi

# Install Logos.
if [[ ! -x $WINEPREFIX/drive_c/users/$USER/AppData/Local/Logos/Logos.exe ]]; then
    echo "Installing Logos."
    mst="$($WINE winepath -w "${REPO}/ou_dedetai/assets/LogosStubFailOK.mst")"
    $WINE msiexec /i "$DOWNLOADS/$LOGOS_MSI_NAME" TRANSFORMS="$mst" || return 1
else
    echo "Logos already installed."
fi