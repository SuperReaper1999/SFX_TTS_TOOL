"""Post-processing for generated dialogue: radio, phone, distant and room voice effects, plus resampling."""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
from scipy import signal

from dsp import apply_filter, resonance_q, reverb_impulse

# Each effect is a small chain: band-limit (two filter stages each for a steeper edge), saturate,
# add hiss and squelch, then reverb. Keys left out are skipped.
VOICE_EFFECTS: dict[str, dict[str, float]] = {
    "None": {},
    "Radio": {"highpass": 300, "lowpass": 3200, "resonance": .25, "drive": .35, "hiss": .015},
    "Walkie-talkie": {"highpass": 500, "lowpass": 2700, "resonance": .35, "drive": .6, "hiss": .03, "squelch": .35},
    "Phone": {"highpass": 350, "lowpass": 3400, "resonance": .1, "drive": .15},
    "Megaphone": {"highpass": 650, "lowpass": 4200, "resonance": .5, "drive": .75, "reverb_mix": .25, "reverb_decay": .7},
    "Distant": {"lowpass": 2200, "dry": .45, "reverb_mix": .6, "reverb_decay": 1.6},
    "Large hall": {"lowpass": 8000, "reverb_mix": .35, "reverb_decay": 2.6},
}
OUTPUT_RATES = ("24000", "44100", "48000")
KOKORO_RATE = 24000


def _band_limit(samples: np.ndarray, effect: dict[str, float], rate: float) -> np.ndarray:
    for _stage in range(2):
        if effect.get("highpass"):
            samples = apply_filter(samples, "highpass", effect["highpass"], math.sqrt(.5), rate)
    for stage in range(2):
        if effect.get("lowpass"):
            # Only the last stage resonates, so the peak stays a single, controlled bump at the cutoff.
            q = resonance_q(effect.get("resonance", 0.0)) if stage == 1 else math.sqrt(.5)
            samples = apply_filter(samples, "lowpass", effect["lowpass"], q, rate)
    return samples


def apply_voice_effect(samples: np.ndarray, rate: int, name: str, seed: int = 0) -> np.ndarray:
    """Return the processed voice at the same peak level as the input (longer if a reverb tail is added)."""
    effect = VOICE_EFFECTS.get(name, {})
    peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
    if not effect or peak <= 0:
        return samples
    rng = np.random.default_rng(seed)
    voice = _band_limit(samples / peak, effect, rate)
    if effect.get("drive"):
        drive = 1 + effect["drive"] * 9
        voice = np.tanh(voice * drive) / math.tanh(drive)
        if effect.get("lowpass"):
            # The speaker or transmitter after the clipping stage rolls off the fizz that clipping adds.
            voice = apply_filter(voice, "lowpass", effect["lowpass"], math.sqrt(.5), rate)
    if effect.get("hiss"):
        voice = voice + _band_limit(rng.normal(0, 1, len(voice)), effect, rate) * effect["hiss"]
    if effect.get("squelch"):
        # A short "kerchunk" as the transmitter keys up, and a burst of static as it releases.
        key_up = _band_limit(rng.normal(0, 1, int(.03 * rate)), effect, rate) * effect["squelch"] * np.linspace(1, 0, int(.03 * rate))
        release_length = int(.16 * rate)
        release = _band_limit(rng.normal(0, 1, release_length), effect, rate) * effect["squelch"] * np.exp(-np.arange(release_length) / (.05 * rate))
        voice = np.concatenate((key_up, np.zeros(int(.04 * rate)), voice, release))
    if effect.get("reverb_mix"):
        tail = int(effect["reverb_decay"] * rate)
        dry = np.concatenate((voice, np.zeros(tail)))
        wet = signal.fftconvolve(dry, reverb_impulse(effect["reverb_decay"], rate, seed + 31))[:len(dry)]
        voice = dry * effect.get("dry", 1 - effect["reverb_mix"] / 2) + wet * effect["reverb_mix"]
    return voice / max(float(np.max(np.abs(voice))), 1e-9) * peak


def resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return samples
    divisor = math.gcd(source_rate, target_rate)
    return signal.resample_poly(samples, target_rate // divisor, source_rate // divisor)


def process_wav(path: Path, effect: str, output_rate: int, seed: int = 0) -> int:
    """Apply ``effect`` to a 16-bit mono WAV in place and resample it to ``output_rate``. Returns the final rate."""
    with wave.open(str(path), "rb") as source:
        rate = source.getframerate()
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError(f"{path.name} is not a 16-bit mono WAV.")
        samples = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(np.float64) / 32767
    if VOICE_EFFECTS.get(effect) or rate != output_rate:
        samples = resample(apply_voice_effect(samples, rate, effect, seed), rate, output_rate)
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(output_rate)
            output.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return output_rate
