"""Cross-platform asynchronous WAV preview playback.

Windows uses the standard-library ``winsound`` module. Linux (including
Kubuntu/KDE Plasma) and macOS hand the file to the first available
command-line player, so no extra Python packages are required.
"""

from __future__ import annotations

import atexit
import shutil
import subprocess
import sys

try:
    import winsound
except ImportError:  # Linux and macOS
    winsound = None

# Tried in order. pw-play ships with PipeWire (Kubuntu 22.10+), paplay with
# PulseAudio/pipewire-pulse, aplay with ALSA, and ffplay with FFmpeg.
LINUX_PLAYERS: tuple[tuple[str, ...], ...] = (
    ("pw-play",),
    ("paplay",),
    ("aplay", "-q"),
    ("ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"),
)
MAC_PLAYERS: tuple[tuple[str, ...], ...] = (("afplay",),)

_process: subprocess.Popen | None = None


def _player_command() -> tuple[str, ...] | None:
    candidates = MAC_PLAYERS if sys.platform == "darwin" else LINUX_PLAYERS
    for command in candidates:
        if shutil.which(command[0]):
            return command
    return None


def is_available() -> bool:
    return winsound is not None or _player_command() is not None


def unavailable_reason() -> str:
    if sys.platform == "darwin":
        return "Preview needs afplay, which should be part of macOS."
    return "Preview needs an audio player: install pipewire-bin (pw-play), pulseaudio-utils (paplay), or alsa-utils (aplay)."


def play_wav(path: str) -> bool:
    """Start playing ``path`` without blocking. Returns False if no player exists."""
    global _process
    stop()
    if winsound is not None:
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        return True
    command = _player_command()
    if command is None:
        return False
    _process = subprocess.Popen([*command, str(path)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def stop() -> None:
    global _process
    if winsound is not None:
        winsound.PlaySound(None, 0)
        return
    if _process is not None:
        if _process.poll() is None:
            _process.terminate()
            try:
                _process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                _process.kill()
        _process = None


atexit.register(stop)
