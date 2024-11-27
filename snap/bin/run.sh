#!/usr/bin/env bash

# Define config variables.
FLPRODUCT=Logos
INSTALLDIR="$SNAP_USER_DATA"
TARGETVERSION=10
TARGET_RELEASE_VERSION="37.2.0.0012"
WINE_EXE="${SNAP}/opt/wine-devel/bin/wine64"

# Ensure correct environment.
if [[ $SNAP_NAME != oudedetai ]]; then
    echo "ERROR: Not running in oudedetai snap environment."
    exit 1
fi

# Ensure config file.
config_file="${SNAP_NAME}.json"
tmp=$(mktemp)
user_config="${SNAP_USER_DATA}/${config_file}"
if [[ ! -r $user_config ]]; then
    cp "${SNAP}/etc/${config_file}" "$user_config"
    jq --arg a "$FLPRODUCT" '.FLPRODUCT = $a' "$user_config" > "$tmp"
    mv "$tmp" "$user_config"
    jq --arg a "$INSTALLDIR" '.INSTALLDIR = $a' "$user_config" > "$tmp"
    mv "$tmp" "$user_config"
    jq --arg a "$TARGETVERSION" '.TARGETVERSION = $a' "$user_config" > "$tmp"
    mv "$tmp" "$user_config"
    jq --arg a "$TARGET_RELEASE_VERSION" '.TARGET_RELEASE_VERSION = $a' "$user_config" > "$tmp"
    mv "$tmp" "$user_config"
    jq --arg a "$WINE_EXE" '.WINE_EXE = $a' "$user_config" > "$tmp"
    mv "$tmp" "$user_config"
fi

# Ensure Logos is installed.
app_exe="$(find "${INSTALLDIR}/wine64_bottle" -wholename "*${FLPRODUCT}/${FLPRODUCT}.exe" 2>/dev/null)"
if [[ -z $app_exe ]]; then
    oudedetai --install-app -PFK $@
    ec=$?
    if [[ $ec -ne 0 ]]; then
        exit $ec
    fi
fi

# Run Logos.
oudedetai --run-installed-app $@
