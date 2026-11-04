"""Meteor log files and the daily count plot.

Files, one set per UTC day, in the output folder:
  meteors_YYYYMMDD.csv  every underdense meteor
  rejects_YYYYMMDD.csv  echoes that failed a test, with the reason (for tuning);
                        noise flickers rejected as too weak are not written
  counts_YYYYMMDD.csv   meteors per 15-minute bin
  counts_YYYYMMDD.png   the same as a bar chart; written once the day is over,
                        or when the program stops
  clips_YYYYMMDD/       audio of each logged echo, from CLIP_BEFORE_S before its
                        peak (tools/plot_clip.py plots one)

Counts already logged today are reloaded at start-up, so restarting the program
during the day does not lose them.
"""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from .config import AUDIO_RATE, PILOT_MHZ

FIELDS = ["utc", "audio_hz", "peak_snr_db", "tau_ms", "rf_mhz", "channel", "peak_dbfs",
          "noise_dbfs", "bin_snr_db", "plateau_ms", "rise_ms", "duration_s", "fit_r2",
          "integrated_snr_s", "env_bw_hz"]
BINS_PER_DAY = 96


def clip_name(utc, audio_hz, accepted):
    """File name of an echo's audio clip, e.g. 184313.244_1065Hz_reject.wav."""
    return (f"{utc:%H%M%S}.{utc.microsecond // 1000:03d}_{audio_hz:.0f}Hz_"
            f"{'meteor' if accepted else 'reject'}.wav")


def _fmt(v, nd):
    return "" if v != v else f"{v:.{nd}f}"   # blank for NaN


class MeteorLog:
    def __init__(self, out_dir, channel, dial_hz, log_rejects=True):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.channel, self.dial_hz, self.log_rejects = channel, dial_hz, log_rejects
        self.counts = {}
        self.saved = set()
        today = datetime.now(timezone.utc).date()
        self.counts[today] = self._reload(today)

    def _reload(self, day):
        counts = np.zeros(BINS_PER_DAY, int)
        path = self.dir / f"meteors_{day:%Y%m%d}.csv"
        if path.exists():
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    t = datetime.fromisoformat(row["utc"].replace("Z", ""))
                    counts[(t.hour * 60 + t.minute) // 15] += 1
        return counts

    def day_counts(self, day):
        if day not in self.counts:
            self.counts[day] = self._reload(day)
        return self.counts[day]

    def add(self, m):
        day = m.utc.date()
        if m.accepted:
            self.day_counts(day)[(m.utc.hour * 60 + m.utc.minute) // 15] += 1
            self.saved.discard(day)   # a late meteor: the day's plot needs redrawing
        elif not self.log_rejects or m.reason.startswith("too weak"):
            return   # noise flickers fail as 'too weak' about twice a second: not logged
        name = "meteors" if m.accepted else "rejects"
        path = self.dir / f"{name}_{day:%Y%m%d}.csv"
        new = not path.exists()
        row = {"utc": m.utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
               "audio_hz": _fmt(m.audio_hz, 1), "peak_snr_db": _fmt(m.peak_snr_db, 1),
               "tau_ms": _fmt(m.tau_ms, 1),
               "rf_mhz": _fmt((self.dial_hz + m.audio_hz) / 1e6, 6),
               "channel": self.channel, "peak_dbfs": _fmt(m.peak_dbfs, 1),
               "noise_dbfs": _fmt(m.noise_dbfs, 1), "bin_snr_db": _fmt(m.bin_snr_db, 1),
               "plateau_ms": _fmt(m.plateau_ms, 0), "rise_ms": _fmt(m.rise_ms, 0),
               "duration_s": _fmt(m.duration_s, 3), "fit_r2": _fmt(m.r2, 3),
               "integrated_snr_s": _fmt(m.integrated_snr_s, 2),
               "env_bw_hz": _fmt(m.env_bw_hz, 1)}
        fields = FIELDS if m.accepted else FIELDS + ["reason"]
        if not m.accepted:
            row["reason"] = m.reason
        if not new:
            # a file begun by an earlier version keeps its own columns
            with open(path, newline="", encoding="utf-8") as f:
                fields = next(csv.reader(f), fields)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow(row)
        if m.clip is not None:
            clips = self.dir / f"clips_{day:%Y%m%d}"
            clips.mkdir(exist_ok=True)
            # 32-bit float keeps the weak signals' full resolution; 1.0 = full scale
            wavfile.write(clips / clip_name(m.utc, m.audio_hz, m.accepted), AUDIO_RATE,
                          m.clip.astype(np.float32))

    def roll_over(self, now=None):
        """Save the plot of any day that ended more than a minute ago."""
        now = now or datetime.now(timezone.utc)
        for day in list(self.counts):
            end = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1)
            if now - end > timedelta(minutes=1) and day not in self.saved:
                self.save_day(day)
        self.day_counts(now.date())

    def close(self):
        """Save every day's counts and plot, including today's so far."""
        for day in list(self.counts):
            if day not in self.saved:
                self.save_day(day)

    def save_day(self, day):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        counts = self.day_counts(day)
        with open(self.dir / f"counts_{day:%Y%m%d}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["bin_start_utc", "meteors"])
            for i, n in enumerate(counts):
                w.writerow([f"{day:%Y-%m-%d}T{i // 4:02d}:{i % 4 * 15:02d}Z", int(n)])

        fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
        ax.bar(np.arange(BINS_PER_DAY) / 4, counts, width=0.25 * 0.85, align="edge",
               color="#2a78d6")
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 2))
        ax.set_xlabel("UTC hour")
        ax.set_ylabel("Meteors per 15 minutes")
        ax.set_title(f"Underdense meteors, {day:%Y-%m-%d} UTC, TV channel {self.channel} "
                     f"({PILOT_MHZ[self.channel]:.3f} MHz): {int(counts.sum())} total")
        ax.grid(axis="y", alpha=0.3)
        fig.savefig(self.dir / f"counts_{day:%Y%m%d}.png", dpi=120)
        plt.close(fig)
        self.saved.add(day)
