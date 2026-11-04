"""Streaming signal processing: decimation, SDR-to-audio conversion, impulse blanking.

Every class here keeps its own state between blocks, so a stream can be fed in
pieces of any size without clicks or gaps at the joins.
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.ndimage import median_filter
from scipy.signal import firwin, lfilter, lfilter_zi

from .config import AUDIO_RATE


def factor_stages(d, largest=25):
    """Split an integer decimation into stages no larger than `largest`."""
    primes, n, p = [], d, 2
    while n > 1:
        while n % p == 0:
            primes.append(p)
            n //= p
        p += 1
    stages = []
    for q in sorted(primes, reverse=True):
        for i, s in enumerate(stages):
            if s * q <= largest:
                stages[i] *= q
                break
        else:
            stages.append(q)
    return sorted(stages, reverse=True)


class FirDecimator:
    """Low-pass filter and keep every d-th sample. Computes only the kept outputs."""

    def __init__(self, d, taps_per_stage=10, gain=1.0):
        self.d = d
        n = taps_per_stage * d + 1
        cutoff = 0.8 / d if d > 1 else 0.9
        self.h = (firwin(n, cutoff) * gain)[::-1].astype(np.float32)
        self.buf = None

    def __call__(self, x):
        if self.buf is None:
            self.buf = np.zeros(len(self.h) - 1, x.dtype)
        xx = np.concatenate((self.buf, x))
        n_out = (len(xx) - len(self.h)) // self.d + 1
        if n_out <= 0:
            self.buf = xx
            return np.zeros(0, x.dtype)
        windows = sliding_window_view(xx, len(self.h))[: n_out * self.d : self.d]
        self.buf = xx[n_out * self.d:]
        return (windows @ self.h).astype(x.dtype)


class Interpolator:
    """Raise the sample rate by an integer factor (for sound cards that refuse 8 kHz)."""

    def __init__(self, up):
        self.up = up
        self.filt = FirDecimator(1, taps_per_stage=1, gain=up)
        self.filt.h = (firwin(16 * up + 1, 0.9 / up) * up)[::-1].astype(np.float32)

    def __call__(self, x):
        z = np.zeros(len(x) * self.up, np.float32)
        z[:: self.up] = x
        return self.filt(z)


class Decimator:
    """Integer decimation in as many stages as needed."""

    def __init__(self, d):
        self.stages = [FirDecimator(s) for s in factor_stages(d)] if d > 1 else []

    def __call__(self, x):
        for s in self.stages:
            x = s(x)
        return x


class SdrToAudio:
    """Complex baseband from an SDR -> 8 kHz upper-sideband audio.

    The SDR is tuned `offset_hz` below the dial frequency (away from the DC
    spike). This shifts the dial frequency to 0 Hz, decimates to 8 kHz, and keeps
    only the 200-3000 Hz above the dial: that is USB demodulation.
    """

    def __init__(self, sample_rate, offset_hz):
        if sample_rate % AUDIO_RATE:
            raise ValueError(f"SDR rate {sample_rate} is not a multiple of {AUDIO_RATE}")
        self.step = -2 * np.pi * offset_hz / sample_rate
        self.phase = 0.0
        self.table = None
        self.decimate = Decimator(int(sample_rate // AUDIO_RATE))
        n = np.arange(255) - 127
        lp = firwin(255, 1400, fs=AUDIO_RATE)
        self.usb = (lp * np.exp(2j * np.pi * 1600 * n / AUDIO_RATE)).astype(np.complex64)
        self.zi = lfilter_zi(self.usb, 1).astype(np.complex64) * 0

    def __call__(self, iq):
        n = len(iq)
        if self.table is None or len(self.table) != n:   # blocks are usually all one size
            self.table = np.exp(1j * self.step * np.arange(n)).astype(np.complex64)
        x = iq.astype(np.complex64) * (self.table * np.complex64(np.exp(1j * self.phase)))
        self.phase = (self.phase + self.step * n) % (2 * np.pi)
        x = self.decimate(x)
        y, self.zi = lfilter(self.usb, 1, x, zi=self.zi)
        return y.real.astype(np.float32)


class AudioDecimator:
    """Real sound-card audio at a multiple of 8 kHz -> 8 kHz."""

    def __init__(self, rate):
        if rate % AUDIO_RATE:
            raise ValueError(f"sound card rate {rate} is not a multiple of {AUDIO_RATE}")
        self.decimate = Decimator(int(rate // AUDIO_RATE))

    def __call__(self, x):
        return self.decimate(x.astype(np.float32))


class Blanker:
    """Zero samples exceeding k times the local RMS, plus a 1 ms guard each side.

    Same rule as the MSK144 analysis: the local mean square comes from an 8 ms
    running median of x^2, which ignores 1-2 ms impulses but follows a real echo.
    A short history from the previous block keeps the median continuous.
    """

    def __init__(self, k=5.0, window_s=0.008, rate=AUDIO_RATE):
        self.k = k
        self.win = int(window_s * rate)
        self.guard = max(1, int(0.001 * rate))
        self.hist = np.zeros(0, np.float32)
        self.n_blanked = 0

    def __call__(self, x):
        if self.k <= 0 or len(x) == 0:
            return x
        xx = np.concatenate((self.hist, x))
        # median of a chi-square(1) variable is 0.455 times its mean
        local_ms = median_filter(xx * xx, size=self.win, mode="nearest") / 0.455
        bad = np.abs(xx) > self.k * np.sqrt(np.maximum(local_ms, 1e-12))
        bad = np.convolve(bad, np.ones(2 * self.guard + 1), "same") > 0
        bad = bad[len(self.hist):]
        self.hist = x[-self.win:].copy()
        if bad.any():
            x = x.copy()
            x[bad] = 0
            self.n_blanked += int(bad.sum())
        return x
