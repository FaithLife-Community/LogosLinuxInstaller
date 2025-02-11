#!/usr/bin/env bash

# This script can be run non-interactively if you set env variables beforehand:
# - LOGOS_WINEPREFIX (e.g. $HOME/wine-logos)
# - LOGOS_WINE (e.g. /opt/wine-devel/bin/wine64)

# Set env variables.
while [[ -z $LOGOS_WINEPREFIX ]]; do
    read -p "Full path to Logos wineprefix directory (variables will not be expanded!): " ans
    if [[ -n $ans ]]; then
        export LOGOS_WINEPREFIX="$ans"
        if [[ ! -d $LOGOS_WINEPREFIX ]]; then
            echo "Error: LOGOS_WINEPREFIX doesn't exist."
            exit 1
        fi
    fi
done
export WINEPREFIX="$LOGOS_WINEPREFIX"

while [[ -z $LOGOS_WINE ]]; do
    read -p "Full path to wine binary (variables will not be expanded!): " ans
    if [[ -n $ans ]]; then
        export LOGOS_WINE="$ans"
        if ! "$LOGOS_WINE" --version >/dev/null 2>&1; then
            echo "Error: Can't run wine binary."
            exit 1
        fi
    fi
done
export LOGOS_WINEDIR="$(dirname $LOGOS_WINE)"
export WINE="$LOGOS_WINE"
export WINELOADER="$LOGOS_WINE"
export WINESERVER="$LOGOS_WINEDIR/wineserver"

# Run installed app.
"$WINE" "$WINEPREFIX/drive_c/users/$USER/AppData/Local/Logos/Logos.exe"