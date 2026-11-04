"""Real-time underdense meteor detection in every frequency bin from 500 to 1500 Hz.

The echo tests and decay fit follow the MSK144 echo analysis in
HamSCI/MSQP (data_analysis/underdense_decay), applied to each FFT bin of a
continuous stream instead of to a whole recording:

1. Impulse noise is blanked in the audio (samples over 5x the local RMS).
2. 1024-point spectra every 16 ms. Each bin keeps its own noise floor (the
   median of its smoothed power over the last minute), so a bin carrying a steady
   direct-path carrier has a high floor and only rises above the carrier count.
3. A burst starts when a bin rises EDGE_DB above its floor and ends when it has
   been back below for MERGE_GAP_S; its peak must reach the threshold.
   Bursts in neighbouring bins at the same time are one meteor (the FFT window
   spreads a tone over 2-3 bins). A burst that lights up a large part of the
   passband at once is impulse noise, not a meteor.
4. For each meteor the audio around the detected frequency is filtered to
   +-25 Hz, and the envelope of that (4 ms steps, far finer than the 128 ms FFT
   window) is fitted with the plateau-then-exponential model. The echo is
   underdense if it lasts under 2 s, rises within 0.2 s, fits with R2 >= 0.4,
   and carries enough energy (integrated SNR) to stand out from noise flickers.

tau is the amplitude e-folding time: A(t) = A0 exp(-t / tau) after the plateau.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.optimize import curve_fit
from scipy.sparse.csgraph import connected_components
from scipy.signal import fftconvolve, firwin, kaiserord

from .config import (AUDIO_RATE, AUDIO_RING_S, BROADBAND_FRACTION, CLIP_AFTER_S,
                     CLIP_BEFORE_S, EDGE_DB, ENV_BW_HZ,
                     ENV_STEP_S, F_HI, F_LO, FFT_SIZE, FIT_TAIL_S, FLOOR_UPDATE_S,
                     FLOOR_WINDOW_S, GROUP_BINS, GROUP_HOLD_S, HOP, MAX_DURATION_S,
                     MAX_PLATEAU_S, MAX_RISE_S, MERGE_GAP_S, MIN_ENV_BW_HZ, MIN_INTEGRATED_SNR_S, MIN_R2,
                     NOISE_BEFORE_S, OWN_CARRIER_HZ,
                     SMOOTH_FRAMES, TAU_RANGE_S, THRESHOLD_DB, WARMUP_S)
from .dsp import Blanker

NAN = float("nan")


@dataclass
class Meteor:
    utc: datetime
    audio_hz: float
    peak_snr_db: float   # envelope peak above the noise just before the echo (+-25 Hz)
    peak_dbfs: float     # envelope peak power; 0 dBFS = full-scale sine
    tau_ms: float        # amplitude e-folding time after the plateau
    plateau_ms: float
    rise_ms: float
    duration_s: float
    r2: float
    integrated_snr_s: float  # echo energy over noise power, summed over the echo
    bin_snr_db: float    # peak in the FFT bin above that bin's floor
    noise_dbfs: float
    accepted: bool
    reason: str
    frame: int           # spectrum number of the peak, for the waterfall marker
    clip: object = None  # audio from CLIP_BEFORE_S before the peak, for saving; not for
                         # noise flickers (too weak) or impulse noise (broadband)
    env_bw_hz: float = NAN  # half-width of the envelope filter used for the fit


@dataclass
class _Burst:
    bin: int
    start: int
    peak: int
    end: int
    peak_snr: float
    long: bool


def decay_power(t, a, tau, knee, pn):
    """Echo power holding at a until t = knee, then decaying as exp(-2(t-knee)/tau)
    (amplitude e-folding tau), plus noise power pn."""
    return a * np.exp(-2 * np.maximum(t - knee, 0) / tau) + pn


class MeteorDetector:
    """Feed 8 kHz audio in blocks; get spectra for display and finished meteors."""

    def __init__(self, threshold_db=THRESHOLD_DB, blank_k=5.0, rate=AUDIO_RATE):
        self.rate = rate
        self.threshold_db = threshold_db
        self.blanker = Blanker(blank_k, rate=rate)
        self.window = np.hanning(FFT_SIZE).astype(np.float32)
        self.scale = 4.0 / float(self.window.sum()) ** 2  # full-scale sine -> 0 dBFS
        freqs = np.fft.rfftfreq(FFT_SIZE, 1 / rate)
        self.bins = np.flatnonzero((freqs >= F_LO) & (freqs <= F_HI))
        self.freqs = freqs[self.bins]
        self.bin_hz = rate / FFT_SIZE
        self.frame_s = HOP / rate
        nb = len(self.bins)

        # audio: frames not yet transformed, and a ring of recent audio for fits
        self.pending = np.zeros(0, np.float32)
        self.ring = np.zeros(int(AUDIO_RING_S * rate), np.float32)
        self.n_samples = 0       # samples received so far
        self.t_offset = None     # UTC (Unix s) of sample 0

        # spectra
        self.frame = 0
        self.recent = np.zeros((SMOOTH_FRAMES, nb))
        self.hist_every = 4
        n_floor = int(FLOOR_WINDOW_S / self.frame_s / self.hist_every)
        self.floor_hist = np.zeros((n_floor, nb), np.float32)
        self.floor_n = 0
        self.floor = np.ones(nb)
        self.next_floor = 0
        n_keep = int(8.0 / self.frame_s)
        self.p_hist = np.zeros((n_keep, nb), np.float32)   # smoothed power
        self.above_count = np.zeros(n_keep, np.int32)   # bins over the threshold

        # bursts, per bin
        self.active = np.zeros(nb, bool)
        self.busy = np.zeros(nb, bool)   # held above after a forced close
        self.b_start = np.zeros(nb, int)
        self.b_peak = np.zeros(nb, int)
        self.b_last = np.zeros(nb, int)
        self.b_snr = np.zeros(nb)
        self.waiting = []
        self.gap = max(1, round(MERGE_GAP_S / self.frame_s))
        self.hold = round(GROUP_HOLD_S / self.frame_s)
        self.max_frames = round(MAX_DURATION_S / self.frame_s)
        self.warmup = round(WARMUP_S / self.frame_s)

        self.env_filters = {}
        self.max_lp = len(self._env_filter(MIN_ENV_BW_HZ))
        self.env_step = int(ENV_STEP_S * rate)

    # ------------------------------------------------------------ input

    def process(self, x, t_first):
        """Add a block of audio whose first sample was at UTC t_first (Unix s).

        Returns (spectra in dBFS, shape (n, bins), number of the first spectrum,
        list of finished Meteor records, accepted and rejected).
        """
        x = np.asarray(x, np.float32)
        self._update_clock(t_first)
        x = self.blanker(x)
        self._store(x)
        self.pending = np.concatenate((self.pending, x))
        n = (len(self.pending) - FFT_SIZE) // HOP + 1
        first = self.frame
        if n <= 0:
            return np.zeros((0, len(self.bins))), first, []
        frames = sliding_window_view(self.pending, FFT_SIZE)[: n * HOP : HOP]
        spec = np.fft.rfft(frames * self.window, axis=1)[:, self.bins]
        power = (spec.real ** 2 + spec.imag ** 2) * self.scale
        self.pending = self.pending[n * HOP:]
        events = []
        for p in power:
            events += self._step(p)
        return 10 * np.log10(power + 1e-20), first, events

    def frame_time(self, frame):
        """UTC (Unix s) of the centre of a spectrum's window."""
        return self.t_offset + (frame * HOP + FFT_SIZE / 2) / self.rate

    def _update_clock(self, t_first):
        # Sample count gives smooth time; the wall clock keeps it honest.
        # Small jitter is averaged out; a jump (dropped audio) resets it.
        est = t_first - self.n_samples / self.rate
        if self.t_offset is None or abs(est - self.t_offset) > 1.0:
            self.t_offset = est
        else:
            self.t_offset += 0.02 * (est - self.t_offset)

    def _store(self, x):
        n = len(self.ring)
        if len(x) >= n:
            x = x[-n:]
        idx = (self.n_samples + np.arange(len(x))) % n
        self.ring[idx] = x
        self.n_samples += len(x)

    def _fetch(self, a, b):
        """Audio samples a..b-1 (absolute numbering), or None if not held."""
        if a < max(0, self.n_samples - len(self.ring)) or b > self.n_samples:
            return None
        return self.ring[np.arange(a, b) % len(self.ring)]

    # ------------------------------------------------------------ spectra

    def _step(self, p):
        f = self.frame
        self.frame += 1
        self.recent[f % SMOOTH_FRAMES] = p
        ps = self.recent.mean(0) if f >= SMOOTH_FRAMES - 1 else p
        if f % self.hist_every == 0:
            self.floor_hist[self.floor_n % len(self.floor_hist)] = ps
            self.floor_n += 1
        if f >= self.next_floor:
            n = min(self.floor_n, len(self.floor_hist))
            self.floor = np.maximum(np.median(self.floor_hist[:n], axis=0), 1e-20)
            self.next_floor = f + round(FLOOR_UPDATE_S / self.frame_s)
        i = f % len(self.p_hist)
        self.p_hist[i] = ps
        snr = 10 * np.log10(ps / self.floor)
        above = snr > EDGE_DB
        self.above_count[i] = int(np.sum(snr > self.threshold_db))
        if f < self.warmup:
            return []

        self.busy &= above
        start = above & ~self.active & ~self.busy
        self.b_start[start] = f
        self.b_peak[start] = f
        self.b_snr[start] = snr[start]
        self.active |= start
        up = self.active & (snr > self.b_snr)
        self.b_snr[up] = snr[up]
        self.b_peak[up] = f
        self.b_last[self.active & above] = f
        too_long = self.active & (f - self.b_start >= self.max_frames)
        close = self.active & ((f - self.b_last > self.gap) | too_long)
        for b in np.flatnonzero(close):
            self.active[b] = False
            if too_long[b]:
                self.busy[b] = True   # wait for it to drop before tracking again
            if self.b_snr[b] >= self.threshold_db:
                self.waiting.append(_Burst(int(b), int(self.b_start[b]), int(self.b_peak[b]),
                                           int(self.b_last[b]), float(self.b_snr[b]),
                                           bool(too_long[b])))
        return self._finish_groups(f)

    def _finish_groups(self, f):
        w = self.waiting
        if not w or min(c.end for c in w) >= f - self.hold:
            return []   # nothing has been quiet long enough to finish
        # Group bursts that are near in frequency and overlap in time, through
        # chains of neighbours. At low thresholds noise keeps hundreds of
        # bursts waiting, so this is done on arrays, not burst by burst.
        b = np.array([c.bin for c in w])
        s = np.array([c.start for c in w])
        e = np.array([c.end for c in w])
        near = ((np.abs(b[:, None] - b[None, :]) <= GROUP_BINS)
                & (s[:, None] <= e[None, :] + self.gap) & (s[None, :] <= e[:, None] + self.gap))
        _, label = connected_components(near, directed=False)
        events = []
        done = set()
        for g in np.unique(label):
            group = [w[i] for i in np.flatnonzero(label == g)]
            end = max(c.end for c in group)
            lo = max(min(c.bin for c in group) - GROUP_BINS, 0)
            hi = max(c.bin for c in group) + GROUP_BINS + 1
            still = self.active[lo:hi] & (self.b_start[lo:hi] <= end + self.gap)
            need = end * HOP + FFT_SIZE + int(FIT_TAIL_S * self.rate) + self.max_lp
            if (any(f - c.end <= self.hold for c in group) or still.any()
                    or self.n_samples < need):
                continue
            for c in group:
                done.add(id(c))
            events.append(self._analyse(group))
        self.waiting = [c for c in self.waiting if id(c) not in done]
        return events

    # ------------------------------------------------------------ one meteor

    def _analyse(self, group):
        best = max(group, key=lambda c: c.peak_snr)
        start, end = min(c.start for c in group), max(c.end for c in group)
        b = best.bin

        # frequency: power-weighted centre of the peak bin and its neighbours
        freq = float(self.freqs[b])
        if self.frame - best.peak < len(self.p_hist):
            row = self.p_hist[best.peak % len(self.p_hist)]
            lo, hi = max(b - 1, 0), min(b + 2, len(row))
            w = np.maximum(row[lo:hi] - self.floor[lo:hi], 0)
            if w.sum() > 0:
                freq = float(np.sum(w * self.freqs[lo:hi]) / w.sum())

        m = Meteor(utc=datetime.fromtimestamp(self.frame_time(best.peak), timezone.utc),
                   audio_hz=freq, peak_snr_db=NAN, peak_dbfs=NAN, tau_ms=NAN,
                   plateau_ms=NAN, rise_ms=NAN, duration_s=(end - start) * self.frame_s,
                   r2=NAN, integrated_snr_s=NAN, bin_snr_db=best.peak_snr, noise_dbfs=NAN, accepted=False,
                   reason="", frame=best.peak)
        n_bins = len(self.bins)
        if self.above_count[best.peak % len(self.above_count)] > BROADBAND_FRACTION * n_bins:
            m.reason = "broadband (impulse noise)"
        elif any(c.long for c in group):
            m.reason = f"too long (over {MAX_DURATION_S:g} s)"
        else:
            self._fit(m, freq, start, end)
            if not m.reason:
                m.accepted = True
        if not m.reason.startswith(("too weak", "broadband")):
            peak = round((m.utc.timestamp() - self.t_offset) * self.rate)
            clip = self._fetch(peak - int(CLIP_BEFORE_S * self.rate),
                               min(peak + int(CLIP_AFTER_S * self.rate), self.n_samples))
            m.clip = None if clip is None else clip.copy()
        return m

    # ------------------------------------------------------------ envelope filter

    def _env_filter(self, cutoff):
        """Low-pass with this cutoff, at least 50 dB down at twice the cutoff."""
        key = round(cutoff, 1)
        if key not in self.env_filters:
            n, beta = kaiserord(50, key / (self.rate / 2))
            self.env_filters[key] = firwin(n | 1, key, window=("kaiser", beta), fs=self.rate)
        return self.env_filters[key]

    def _carriers(self):
        """Frequencies of steady carriers: bins whose floor stands 10 dB above the median."""
        fl = self.floor
        base = np.median(fl)
        found = []
        for i in np.flatnonzero(fl > 10 * base):
            if fl[i] >= fl[max(i - 1, 0)] and fl[i] >= fl[min(i + 1, len(fl) - 1)]:
                lo, hi = max(i - 1, 0), min(i + 2, len(fl))
                w = fl[lo:hi] - base
                found.append(float(np.sum(w * self.freqs[lo:hi]) / w.sum()))
        return found

    def _envelope_cutoff(self, freq):
        """Half the distance to the nearest other carrier, at most ENV_BW_HZ.

        A carrier within OWN_CARRIER_HZ is taken to be the echo's own
        transmitter heard directly; no filter can separate the two.
        """
        d = [abs(c - freq) for c in self._carriers() if abs(c - freq) > OWN_CARRIER_HZ]
        return float(np.clip(min(d) / 2, MIN_ENV_BW_HZ, ENV_BW_HZ)) if d else ENV_BW_HZ

    # ------------------------------------------------------------ fit

    def _fit(self, m, freq, start, end):
        r = self.rate
        m.env_bw_hz = self._envelope_cutoff(freq)
        lp = self._env_filter(m.env_bw_hz)
        centre0 = start * HOP + FFT_SIZE // 2
        a = centre0 - int(NOISE_BEFORE_S[0] * r) - len(lp)
        b = end * HOP + FFT_SIZE + int(FIT_TAIL_S * r) + len(lp) // 2
        seg = self._fetch(a, b)
        if seg is None:
            m.reason = "audio no longer held"
            return
        n = np.arange(a, b)
        y = fftconvolve(seg * np.exp(-2j * np.pi * freq * n / r), lp, "same")
        step = self.env_step
        pw = 4 * np.abs(y[::step]) ** 2          # a full-scale sine gives 1
        ts = (a + np.arange(len(pw)) * step) / r  # seconds since sample 0

        t_on = centre0 / r
        nsel = (ts >= t_on - NOISE_BEFORE_S[0]) & (ts < t_on - NOISE_BEFORE_S[1])
        pn = float(np.mean(pw[nsel])) if nsel.any() else 0.0
        if pn <= 0:
            m.reason = "no noise reference"
            return
        m.noise_dbfs = 10 * np.log10(pn)

        in_echo = np.flatnonzero((ts >= start * HOP / r) & (ts <= (end * HOP + FFT_SIZE) / r))
        ip = int(in_echo[np.argmax(pw[in_echo])])
        m.peak_dbfs = 10 * np.log10(pw[ip])
        m.peak_snr_db = 10 * np.log10(pw[ip] / pn)
        m.utc = datetime.fromtimestamp(self.t_offset + ts[ip], timezone.utc)

        # onset, end and duration on a 25 ms smoothed envelope
        k = max(1, round(0.025 / ENV_STEP_S))
        ss = 10 * np.log10(np.maximum(np.convolve(pw, np.ones(k) / k, "same"), 1e-20) / pn)
        below = ss <= EDGE_DB
        before = np.flatnonzero(below[: ip + 1])
        i_on = int(before[-1]) if before.size else 0
        gap = max(1, round(MERGE_GAP_S / ENV_STEP_S))
        quiet = np.convolve(below[ip:].astype(int), np.ones(gap, int), "valid") == gap
        i_end = ip + int(np.argmax(quiet)) - 1 if quiet.any() else len(pw) - 1
        i_end = max(i_end, ip)
        m.rise_ms = 1000 * (ts[ip] - ts[i_on])
        m.duration_s = ts[i_end] - ts[i_on]

        stop = min(i_end + round(FIT_TAIL_S / ENV_STEP_S), len(pw) - 1)
        tt, yy = ts[ip:stop + 1] - ts[ip], pw[ip:stop + 1]
        if len(tt) < 6:
            m.reason = "too few points to fit"
            return
        # The integrated SNR below sums part of this; if even the whole falls
        # short, skip the fit. Most noise flickers end here, and at low
        # thresholds there are many of them each second.
        bound = float(np.sum(np.maximum(yy - pn, 0)) / pn * ENV_STEP_S)
        if (bound < MIN_INTEGRATED_SNR_S and m.duration_s < MAX_DURATION_S
                and m.rise_ms <= 1000 * MAX_RISE_S):
            m.integrated_snr_s = bound
            m.reason = f"too weak (integrated SNR under {bound:.2f} s)"
            return
        span = ts[i_end] - ts[ip]
        a0 = max(np.mean(yy[:3]) - pn, pn)
        ys = np.convolve(yy, np.ones(k) / k, "same")
        drop = np.flatnonzero(ys < ys[: 3 * k].max() / 10 ** 0.15)
        knee_max = max(min(span, MAX_PLATEAU_S), 2 * ENV_STEP_S)
        knee0 = min(tt[drop[0]] if drop.size else 0.0, 0.9 * knee_max)
        tau_guess = min(max((span - knee0) / 2, 0.01), 0.9 * TAU_RANGE_S[1])

        # Goodness of fit in dB, with data and model both smoothed by 25 ms.
        smooth = lambda v: np.maximum(np.convolve(v, np.ones(k) / k, "valid"), 1e-20)
        yd = 10 * np.log10(smooth(yy))
        spread = np.sum((yd - yd.mean()) ** 2)

        def r2_of(model):
            md = 10 * np.log10(smooth(model))
            return 1 - np.sum((yd - md) ** 2) / spread if yd.size > 2 and spread > 0 else NAN

        # From a single starting point the fit can settle on a poor answer, so
        # start it from several decay times and keep the best fit in dB.
        best = None
        for tau0 in sorted({tau_guess, 0.02, 0.1, 0.5}):
            try:
                # weight each point by the model's own level: power scatter grows with power
                sigma = np.ones_like(yy)
                p0 = (a0, tau0, knee0)
                for _ in range(2):
                    p0, _ = curve_fit(
                        lambda x, amp, tau, knee: decay_power(x, amp, tau, knee, pn),
                        tt, yy, p0=p0, sigma=sigma,
                        bounds=((0, TAU_RANGE_S[0], 0), (np.inf, TAU_RANGE_S[1], knee_max)))
                    sigma = decay_power(tt, *p0, pn)
            except (RuntimeError, ValueError):
                continue
            r2 = r2_of(decay_power(tt, *p0, pn))
            if best is None or r2 > best[0] or best[0] != best[0]:   # NaN loses
                best = (r2, *p0)
        if best is None:
            m.reason = "fit did not converge"
            return
        r2, amp, tau, knee = best
        model = decay_power(tt, amp, tau, knee, pn)
        # Integrated SNR: echo power above the noise, in units of the noise
        # power, summed over the time the fitted echo stands above the noise.
        # A noise flicker in one bin can fit a brief decay well, but it never
        # carries much energy; this is the test that separates the two.
        above = np.flatnonzero(model - pn >= pn)
        n_int = above[-1] + 1 if above.size else 1
        m.integrated_snr_s = float(np.sum(np.maximum(yy[:n_int] - pn, 0)) / pn * ENV_STEP_S)
        m.tau_ms, m.plateau_ms, m.r2 = 1000 * tau, 1000 * knee, r2

        if m.duration_s >= MAX_DURATION_S:
            m.reason = f"too long ({m.duration_s:.2f} s)"
        elif m.rise_ms > 1000 * MAX_RISE_S:
            m.reason = f"slow rise ({m.rise_ms / 1000:.2f} s)"
        elif m.integrated_snr_s < MIN_INTEGRATED_SNR_S:
            m.reason = f"too weak (integrated SNR {m.integrated_snr_s:.2f} s)"
        elif not r2 >= MIN_R2:
            m.reason = f"not exponential (R2 {r2:.2f})"
        elif tau >= TAU_RANGE_S[1] * 0.99:
            m.reason = "decay too slow"
