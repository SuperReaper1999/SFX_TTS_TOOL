"""Filters and reverb shared by the SFX designer and Dialogue Studio's voice effects."""

from __future__ import annotations

import math

import numpy as np
from scipy import signal


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


REVERB_PREDELAY_SECONDS = 0.012


def biquad_coefficients(mode: str, frequency: float, q: float, rate: float) -> tuple[np.ndarray, np.ndarray]:
    """Return normalised (b, a) for an RBJ cookbook low-pass, high-pass, band-pass (0 dB peak) or notch filter."""
    frequency = clamp(frequency, 10.0, rate * 0.45)
    omega = math.tau * frequency / rate
    cosine, alpha = math.cos(omega), math.sin(omega) / (2.0 * q)
    if mode == "highpass":
        b = ((1 + cosine) / 2, -(1 + cosine), (1 + cosine) / 2)
    elif mode == "bandpass":
        b = (alpha, 0.0, -alpha)
    elif mode == "notch":
        b = (1.0, -2 * cosine, 1.0)
    else:
        b = ((1 - cosine) / 2, 1 - cosine, (1 - cosine) / 2)
    a = (1 + alpha, -2 * cosine, 1 - alpha)
    return np.array(b) / a[0], np.array(a) / a[0]


def resonance_q(resonance: float) -> float:
    """Map the 0-0.99 resonance control to Q: 0.71 (no peak) up to about 11 (a sharp +21 dB peak)."""
    return math.sqrt(0.5) * 16.0 ** resonance


def apply_filter(samples: np.ndarray, mode: str, cutoff: np.ndarray | float, q: float, rate: float) -> np.ndarray:
    """Filter with a fixed cutoff, or a per-sample cutoff array updated every millisecond."""
    if np.isscalar(cutoff):
        return signal.lfilter(*biquad_coefficients(mode, float(cutoff), q, rate), samples)
    output = np.empty_like(samples)
    state = np.zeros(2)
    block = max(32, int(rate // 1000))
    for start in range(0, len(samples), block):
        stop = min(start + block, len(samples))
        b, a = biquad_coefficients(mode, float(cutoff[(start + stop) // 2]), q, rate)
        output[start:stop], state = signal.lfilter(b, a, samples[start:stop], zi=state)
    return output


def reverb_impulse(decay_seconds: float, rate: float, seed: int) -> np.ndarray:
    """A deterministic, energy-normalised room tail: decaying noise reaching -60 dB at decay_seconds, darkened above 6 kHz."""
    predelay = int(REVERB_PREDELAY_SECONDS * rate)
    length = max(1, int(decay_seconds * rate))
    tail = np.random.default_rng(seed).normal(0, 1, length) * 10.0 ** (-3.0 * np.arange(length) / length)
    tail = signal.lfilter(*biquad_coefficients("lowpass", 6000.0, math.sqrt(0.5), rate), tail)
    impulse = np.concatenate((np.zeros(predelay), tail))
    return impulse / max(float(np.sqrt(np.sum(impulse ** 2))), 1e-12)
