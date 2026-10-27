#!/usr/bin/env bash
# Linux (Kubuntu) launcher for SFX TTS Tool.
# First run creates a private virtual environment in .venv and installs NumPy into it.
set -euo pipefail
TOOL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$TOOL_ROOT"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Python 3 was not found. Install it with: sudo apt install python3 python3-venv python3-tk"
    exit 1
fi
VENV="$TOOL_ROOT/.venv"
if [ ! -x "$VENV/bin/python" ]; then
    echo "Creating virtual environment in $VENV ..."
    if ! "$PYTHON" -m venv "$VENV"; then
        echo "Could not create the virtual environment. Install it with: sudo apt install python3-venv"
        exit 1
    fi
fi
if ! "$VENV/bin/python" -c "import numpy" >/dev/null 2>&1; then
    echo "Installing NumPy into $VENV ..."
    "$VENV/bin/python" -m pip install -r "$TOOL_ROOT/requirements.txt"
fi
# Tkinter may be system-wide or extracted into .venv, so check it with the venv's Python.
if ! "$VENV/bin/python" -c "import tkinter" >/dev/null 2>&1; then
    echo "Tkinter is missing. Install it with: sudo apt install python3-tk"
    exit 1
fi

exec "$VENV/bin/python" "$TOOL_ROOT/sine_sfx_designer.py" "$@"
