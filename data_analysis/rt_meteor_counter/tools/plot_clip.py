"""Plot a saved echo clip: its spectrogram, and its envelope with the logged fit.

    python tools/plot_clip.py RT_meteor_counter_data/clips_20261102/184313.244_1065Hz_reject.wav

The clip's row is looked up in the meteors or rejects file of the same day, one
folder up. The envelope is recomputed the way the detector computes it, with the
filter width it logged (env_bw_hz; +-25 Hz in older logs, or --bw); the fitted model is drawn
from the logged tau, plateau, peak and noise levels. The plot is saved beside
the clip as a .png.
"""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve, spectrogram

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rt_meteor_counter.config import (CLIP_BEFORE_S, EDGE_DB, ENV_BW_HZ, ENV_STEP_S,  # noqa: E402
                                      FFT_SIZE, HOP)
from rt_meteor_counter.detector import MeteorDetector, decay_power  # noqa: E402


def find_row(clip):
    """The log row whose time and frequency match the clip's name."""
    hms, hz, kind = clip.stem.split("_")
    day = clip.parent.name.split("_")[1]
    name = "meteors" if kind == "meteor" else "rejects"
    path = clip.parent.parent / f"{name}_{day}.csv"
    want = f"{day[:4]}-{day[4:6]}-{day[6:]}T{hms[:2]}:{hms[2:4]}:{hms[4:]}Z"
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["utc"] == want and abs(float(row["audio_hz"]) - float(hz[:-2])) < 1:
                return row
    raise SystemExit(f"no row for {clip.name} in {path}")


def num(row, key):
    return float(row[key]) if row.get(key) else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--bw", type=float,
                    help="envelope filter half-width, Hz (default: as logged, else "
                         f"{ENV_BW_HZ:g})")
    ap.add_argument("--show", action="store_true", help="also open the plot on screen")
    args = ap.parse_args()

    import matplotlib
    if not args.show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    clip = Path(args.clip).resolve()   # find_row needs the folder names
    row = find_row(clip)
    rate, x = wavfile.read(clip)
    x = x.astype(np.float64)
    hz = num(row, "audio_hz")
    t = np.arange(len(x)) / rate - CLIP_BEFORE_S   # seconds from the logged peak

    # envelope, as in the detector
    bw = args.bw or num(row, "env_bw_hz")
    bw = bw if bw > 0 else ENV_BW_HZ
    lp = MeteorDetector(rate=rate)._env_filter(bw)
    y = fftconvolve(x * np.exp(-2j * np.pi * hz * np.arange(len(x)) / rate), lp, "same")
    step = int(ENV_STEP_S * rate)
    edge = len(lp) // 2            # filter start-up at both ends
    keep = slice(edge, len(y) - edge, step)
    te, pw = t[keep], 4 * np.abs(y[keep]) ** 2
    pn = 10 ** (num(row, "noise_dbfs") / 10)
    if not pn > 0:
        pn = np.median(pw[te < -0.3])
    k = max(1, round(0.025 / ENV_STEP_S))
    smooth = np.convolve(pw, np.ones(k) / k, "same")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    f, ts, s = spectrogram(x, rate, window="hann", nperseg=FFT_SIZE, noverlap=FFT_SIZE - HOP)
    band = (f >= hz - 150) & (f <= hz + 150)
    sdb = 10 * np.log10(s[band] + 1e-20)
    ax1.pcolormesh(ts - CLIP_BEFORE_S, f[band], sdb, cmap="inferno", shading="auto",
                   vmin=np.percentile(sdb, 20), vmax=sdb.max())
    ax1.axhline(hz, color="#00e5ff", lw=0.8, ls=":")
    ax1.set_ylabel("Audio frequency (Hz)")
    ax1.set_title(f"{row['utc']}  {hz:.1f} Hz  ({row.get('reason') or 'accepted'})\n"
                  f"tau {row['tau_ms'] or '-'} ms, plateau {row['plateau_ms'] or '-'} ms, "
                  f"R2 {row['fit_r2'] or '-'}, integrated SNR {row['integrated_snr_s'] or '-'} s, "
                  f"peak {row['peak_snr_db'] or '-'} dB", fontsize=10)

    ax2.plot(te, 10 * np.log10(pw / pn), color="#9aa3ad", lw=0.6, label="envelope, 4 ms")
    ax2.plot(te, 10 * np.log10(np.maximum(smooth, 1e-20) / pn), color="#2a78d6", lw=1.5,
             label="envelope, 25 ms smoothed")
    tau, knee = num(row, "tau_ms") / 1000, num(row, "plateau_ms") / 1000
    peak = 10 ** (num(row, "peak_dbfs") / 10)
    if tau > 0 and peak > pn:
        tm = np.linspace(0, te[-1], 400)
        # The fitted amplitude is not logged; the logged peak stands in for it.
        model = decay_power(tm, peak - pn, tau, knee, pn)
        ax2.plot(tm, 10 * np.log10(model / pn), color="#e8590c", lw=2,
                 label="logged fit (amplitude from the peak)")
    ax2.axhline(EDGE_DB, color="#555", lw=0.8, ls="--", label=f"edge, {EDGE_DB:g} dB")
    ax2.axhline(0, color="#555", lw=0.8)
    ax2.set_ylim(-10, max(10 * np.log10(pw.max() / pn) + 3, 15))
    ax2.set_xlabel("Seconds from the logged peak")
    ax2.set_ylabel(f"Power above noise, dB (+-{bw:g} Hz)")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(alpha=0.3)

    out = clip.with_suffix(".png")
    fig.savefig(out, dpi=110)
    print(f"saved {out}")
    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
