#!/usr/bin/env bash
# Linux (Kubuntu) equivalent of "Install Local Kokoro TTS.bat".
# Installs Kokoro beneath this tool folder (.local-tts); the model downloads into .kokoro-cache on first use.
set -euo pipefail
TOOL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHONUSERBASE="$TOOL_ROOT/.local-tts"
export PIP_CACHE_DIR="$TOOL_ROOT/.installer-cache"
export TMPDIR="$TOOL_ROOT/.installer-temp"
mkdir -p "$PYTHONUSERBASE" "$TMPDIR"

PYTHON="$TOOL_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    echo "Missing $TOOL_ROOT/.venv. Run ./run-sfx-designer.sh once before this installer."
    exit 1
fi

if ! "$PYTHON" -m pip install --no-cache-dir --target "$PYTHONUSERBASE" -r "$TOOL_ROOT/requirements-kokoro.txt"; then
    echo
    echo "Local Kokoro installation failed."
    exit 1
fi
echo
echo "Kokoro installed beneath $PYTHONUSERBASE"
echo "Model files download into $TOOL_ROOT/.kokoro-cache on the first generated line."
