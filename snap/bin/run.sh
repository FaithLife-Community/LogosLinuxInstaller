#!/usr/bin/env bash

# Ensure correct environment.
if [[ $SNAP_NAME != oudedetai ]]; then
    echo "ERROR: Not running in oudedetai snap environment."
    exit 1
fi
TARGETVERSION="10"
INSTALLDIR="$SNAP_USER_COMMON"
WINE_EXE="$SNAP/bin/wine64"

# Set from snapcraft.yaml.
msg="ERROR: Empty env variable:"
if [[ -z $FLPRODUCT ]]; then
    echo "$msg FLPRODUCT"
    exit 1
elif [[ -z $TARGET_RELEASE_VERSION ]]; then
    echo "$msg TARGET_RELEASE_VERSION"
    exit 1
fi


# Ensure config file.
config_dir="$SNAP_USER_DATA/.config/FaithLife-Community"
mkdir -p "$config_dir"
CONFIG_FILE="${config_dir}/${SNAP_NAME}.json"
if [[ ! -r $CONFIG_FILE ]]; then
    echo '{}' > "$CONFIG_FILE"
    tmp=$(mktemp)
    jq --arg a "$FLPRODUCT" '.faithlife_product = $a' "$CONFIG_FILE" > "$tmp"
    mv "$tmp" "$CONFIG_FILE"
    jq --arg a "$TARGET_RELEASE_VERSION" '.faithlife_product_release = $a' "$CONFIG_FILE" > "$tmp"
    mv "$tmp" "$CONFIG_FILE"
    jq --arg a "$TARGETVERSION" '.faithlife_product_version = $a' "$CONFIG_FILE" > "$tmp"
    mv "$tmp" "$CONFIG_FILE"
    jq --arg a "$INSTALLDIR" '.install_dir = $a' "$CONFIG_FILE" > "$tmp"
    mv "$tmp" "$CONFIG_FILE"
    jq --arg a "$WINE_EXE" '.wine_binary = $a' "$CONFIG_FILE" > "$tmp"
    mv "$tmp" "$CONFIG_FILE"
fi

# Ensure Logos is installed.
app_exe="$(find "${INSTALLDIR}/wine64_bottle" -wholename "*${FLPRODUCT}/${FLPRODUCT}.exe" 2>/dev/null)"
if [[ -z $app_exe ]]; then
    oudedetai --install-app --skip-dependencies $@
    ec=$?
    if [[ $ec -ne 0 ]]; then
        exit $ec
    fi
fi

# Run Logos.
oudedetai --run-installed-app $@
