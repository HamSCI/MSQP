"""Redraw the decay-time-by-band plots from echoes.csv, without reprocessing WAV files.

Writes, beside the CSV:
  tau_by_band.png        amplitude e-folding time tau, as fitted
  tau_power_by_band.png  power e-folding time tau / 2, the convention used for
                         underdense decay times and diffusion coefficients

Usage:
    python plot_tau_by_band.py data/results/echoes.csv
"""

import argparse
import csv
from pathlib import Path

from underdense_decay import plot_band_summary


def read_echoes(csv_path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["underdense"] = r["underdense"] == "True"
            r["freq_mhz"] = float(r["freq_mhz"])
            r["tau_ms"] = float(r["tau_ms"]) if r["tau_ms"] else float("nan")
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path, help="echoes.csv from underdense_decay.py")
    args = ap.parse_args()

    rows = read_echoes(args.csv)
    out = args.csv.parent
    plot_band_summary(rows, out / "tau_by_band.png")
    plot_band_summary(rows, out / "tau_power_by_band.png", power=True)
    print(f"tau_by_band.png and tau_power_by_band.png written to {out}")


if __name__ == "__main__":
    main()
