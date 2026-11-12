"""Speaker output: the received audio plus a beep at each meteor's frequency.

The playback level is set by a slow automatic gain control so the speaker stays
comfortable. This affects only what you hear; detection always works on the
unaltered audio, so decay times are not distorted.
"""

import threading
from collections import deque

import numpy as np

from .config import AUDIO_RATE
from .dsp import Interpolator

PREFILL_S = 0.2   # buffered audio before playback starts (absorbs block jitter)
MAX_LAG_S = 0.6   # drop old audio beyond this, so playback never falls far behind
TARGET_RMS = 0.1
BEEP_DELAY_S = 0.5   # the beep follows the meteor's own sound, so the echo is heard first


class AudioPlayer:
    def __init__(self, device, volume=0.5, beep_volume=0.3, beep=True):
        self.device = device
        self.volume, self.beep_volume, self.beep_on = volume, beep_volume, beep
        self.level = None
        self.beep_left = np.zeros(0, np.float32)
        self.chunks = deque()
        self.buffered = 0
        self.playing = False
        self.lock = threading.Lock()
        self.stream = None

    def start(self):
        import sounddevice as sd
        for rate, up in ((AUDIO_RATE, 1), (48000, 6), (16000, 2), (24000, 3), (32000, 4)):
            try:
                sd.check_output_settings(device=self.device, samplerate=rate, channels=1)
                break
            except Exception:
                continue
        else:
            raise RuntimeError("the audio output offers no rate that is a multiple of 8 kHz")
        self.rate = rate
        self.interp = Interpolator(up) if up > 1 else None
        self.stream = sd.OutputStream(device=self.device, samplerate=rate, channels=1,
                                      dtype="float32", callback=self._callback)
        self.stream.start()

    def write(self, x):
        """Queue a block of 8 kHz audio for the speaker."""
        if len(x) == 0:
            return
        rms = float(np.sqrt(np.mean(x * x)))
        self.level = rms if self.level is None else 0.95 * self.level + 0.05 * rms
        y = x * (TARGET_RMS / max(self.level, 1e-9)) * self.volume
        if len(self.beep_left):
            n = min(len(y), len(self.beep_left))
            y[:n] += self.beep_left[:n]
            self.beep_left = self.beep_left[n:]
        y = np.clip(y, -1, 1).astype(np.float32)
        if self.interp:
            y = self.interp(y)
        with self.lock:
            self.chunks.append(y)
            self.buffered += len(y)
            while self.buffered > MAX_LAG_S * self.rate and len(self.chunks) > 1:
                self.buffered -= len(self.chunks.popleft())

    def beep(self, hz, duration_s=0.12):
        """Sound a short tone at the meteor's own audio frequency, BEEP_DELAY_S from now."""
        if not self.beep_on:
            return
        n = int(duration_s * AUDIO_RATE)
        tone = np.sin(2 * np.pi * hz * np.arange(n) / AUDIO_RATE) * np.hanning(n)
        start = int(BEEP_DELAY_S * AUDIO_RATE)
        # mixed into the outgoing audio sample by sample; overlapping beeps add
        left = np.zeros(max(len(self.beep_left), start + n), np.float32)
        left[:len(self.beep_left)] = self.beep_left
        left[start:start + n] += (tone * self.beep_volume).astype(np.float32)
        self.beep_left = left

    def _callback(self, outdata, frames, time_info, status):
        out = outdata[:, 0]
        out[:] = 0
        with self.lock:
            if not self.playing and self.buffered >= PREFILL_S * self.rate:
                self.playing = True
            if not self.playing:
                return
            i = 0
            while i < frames and self.chunks:
                c = self.chunks[0]
                n = min(frames - i, len(c))
                out[i:i + n] = c[:n]
                i += n
                self.buffered -= n
                if n == len(c):
                    self.chunks.popleft()
                else:
                    self.chunks[0] = c[n:]
            if i < frames:
                self.playing = False   # ran dry: refill before resuming

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
