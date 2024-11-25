#!/usr/bin/env bash

# Ensure correct environment.
if [[ $SNAP_NAME != oudedetai ]]; then
    echo "ERROR: Not running in oudedetai snap environment."
    exit 1
fi

if [[ $# -gt 0 ]]; then
    # Run oudedetai command directly with given args.
    oudedetai $@
else  # run Logos after ensuring installation
    # Ensure config file.
    if [[ ! -r ${SNAP_USER_COMMON}/${SNAP_NAME}.json ]]; then
        cp $SNAP/etc/${SNAP_NAME}.json ${SNAP_USER_COMMON}/${SNAP_NAME}.json
    fi

    # Ensure Logos is installed.
    app_exe="$(find "${SNAP_USER_COMMON}/wine64_bottle" -wholename '*Logos/Logos.exe' 2>/dev/null)"
    if [[ -z $app_exe ]]; then
        oudedetai --install-app -PFK
        ec=$?
        if [[ $ec -ne 0 ]]; then
            exit $ec
        fi
    fi

    # Run Logos.
    oudedetai --run-installed-app
fi