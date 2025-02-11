#!/usr/bin/env bash

# Ensure correct environment.
if [[ $SNAP_NAME != oudedetai ]]; then
    echo "ERROR: Not running in oudedetai snap environment."
    exit 1
fi

export FLPRODUCT="$1"
shift
echo "Starting $FLPRODUCT"
export TARGETVERSION="10"

# Ensure Faithlife app is installed.
app_exe="$(find "${INSTALLDIR}/wine64_bottle" -wholename "*${FLPRODUCT}/${FLPRODUCT}.exe" 2>/dev/null)"
if [[ -z $app_exe ]]; then
    oudedetai --install-app --assume-yes $@
    ec=$?
    if [[ $ec -ne 0 ]]; then
        exit $ec
    fi
fi

# Run Faithlife app.
oudedetai --run-installed-app $@
