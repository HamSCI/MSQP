"""Compare the detector's output for a synthetic recording with its truth table.

    python -m rt_meteor_counter --wav test.wav --start-utc 2026-01-01T00:00:00 --out out
    python tools/check_detections.py test_truth.csv out 2026-01-01T00:00:00

An echo counts as found if a logged meteor peaks within 0.3 s and 10 Hz of it.
"""

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("truth")
    ap.add_argument("out_dir")
    ap.add_argument("start_utc")
    args = ap.parse_args()

    t0 = datetime.fromisoformat(args.start_utc).replace(tzinfo=timezone.utc).timestamp()
    sec = lambda r: datetime.fromisoformat(r["utc"].replace("Z", "+00:00")).timestamp() - t0
    found = [dict(r, t=sec(r)) for p in Path(args.out_dir).glob("meteors_*.csv") for r in load(p)]
    rejected = [dict(r, t=sec(r)) for p in Path(args.out_dir).glob("rejects_*.csv") for r in load(p)]
    truth = load(args.truth) if Path(args.truth).exists() else []

    def match(r, pool):
        best = [m for m in pool if abs(m["t"] - float(r["t_s"])) < 0.3
                and abs(float(m["audio_hz"]) - float(r["audio_hz"])) < 10]
        return min(best, key=lambda m: abs(m["t"] - float(r["t_s"]))) if best else None

    used = set()
    rows = []
    for r in truth:
        m = match(r, found)
        if m:
            used.add(id(m))
        rows.append((r, m, None if m else match(r, rejected)))

    ud = [x for x in rows if x[0]["kind"] == "underdense"]
    print(f"truth: {len(truth)} echoes, {len(ud)} underdense; logged: {len(found)} meteors")
    print("\nunderdense echoes found, by envelope SNR:")
    for lo, hi in ((5, 10), (10, 15), (15, 20), (20, 26)):
        sel = [x for x in ud if lo <= float(x[0]["snr_db"]) < hi]
        if sel:
            print(f"  {lo:2d}-{hi:2d} dB: {sum(x[1] is not None for x in sel):3d} of {len(sel)}")
    on = [x for x in ud if x[0]["on_carrier"] == "True"]
    print(f"  on the carrier frequency: {sum(x[1] is not None for x in on)} of {len(on)}")

    longs = [x for x in rows if x[0]["kind"] == "long"]
    print(f"\nlong echoes wrongly accepted: {sum(x[1] is not None for x in longs)} of {len(longs)}")
    false = [m for m in found if id(m) not in used]
    print(f"logged meteors matching no echo (false alarms): {len(false)}")
    for m in false[:10]:
        print(f"    t={m['t']:.2f} s  {m['audio_hz']} Hz  snr {m['peak_snr_db']} dB  "
              f"tau {m['tau_ms']} ms  R2 {m['fit_r2']}")

    good = [(float(r["tau_ms"]), float(m["tau_ms"]), float(r["snr_db"]), r)
            for r, m, _ in ud if m]
    if good:
        ratio = np.array([b / a for a, b, _, _ in good])
        print(f"\nfitted tau / true tau: median {np.median(ratio):.2f}, "
              f"middle half {np.percentile(ratio, 25):.2f}-{np.percentile(ratio, 75):.2f}")
        for lo, hi in ((0, 50), (50, 100), (100, 200), (200, 600)):
            sel = ratio[[lo <= a < hi for a, _, _, _ in good]]
            if sel.size:
                print(f"  true tau {lo:3d}-{hi:3d} ms: median ratio {np.median(sel):.2f} (n={sel.size})")
        freq_err = [float(m["audio_hz"]) - float(r["audio_hz"]) for r, m, _ in ud if m]
        print(f"frequency error: median {np.median(freq_err):+.1f} Hz, "
              f"rms {np.sqrt(np.mean(np.square(freq_err))):.1f} Hz")

    missed = [(r, rej) for r, m, rej in ud if m is None]
    print(f"\nmissed underdense echoes: {len(missed)}; rejected as:")
    reasons = {}
    for r, rej in missed:
        key = rej["reason"].split(" (")[0] if rej else "not detected"
        reasons[key] = reasons.get(key, 0) + 1
    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
