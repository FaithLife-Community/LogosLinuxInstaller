#!/usr/bin/env bash
# Install & run Logos.

# Ensure config file.
if [[ ! -r ${SNAP_USER_COMMON}/${SNAP_NAME}.json ]]; then
    cp $SNAP/etc/default-config.json ${SNAP_USER_COMMON}/${SNAP_NAME}.json
fi

# Ensure Logos is installed.
app_exe="$(find "${SNAP_USER_COMMON}/wine64_bottle" -wholename '*Logos/Logos.exe')"
if [[ -z $app_exe ]]; then
    oudedetai --install-app -PFK
    ec=$?
    if [[ $ec -ne 0 ]]; then
        exit $ec
    fi
fi

# Run Logos.
oudedetai --run-installed-app