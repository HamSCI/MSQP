"""Find echoes seen at the same time on more than one band, from underdense_decay.py output.

Two echoes on different bands are paired when their peak times (echo_utc) are
within --tolerance seconds of each other (default 2 s; the receiving PCs' clocks
agree to about a second). Linked pairs form one event, so an event can hold
several echoes on a band if each is matched by an echo on another band.
Echoes on the same band are never paired with each other.

The output CSV has the same columns as echoes.csv, preceded by:
  event_id      events numbered in time order
  event_bands   the bands in the event, e.g. "10m+6m"
  offset_s      this echo's time after the event's first echo

Every echo is included, whether or not it passed the underdense test; filter on
the underdense column to keep only underdense echoes.

Usage:
    python coincident_echoes.py data/results/echoes.csv
"""

import argparse
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

BAND_ORDER = ["10m", "6m", "2m", "1.25m", "70cm"]


def read_echoes(csv_path):
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["_t"] = datetime.strptime(r["echo_utc"], "%Y-%m-%d %H:%M:%S.%f").timestamp()
    rows.sort(key=lambda r: r["_t"])
    return rows


def find_events(rows, tol):
    """Group rows into events of cross-band pairs within tol seconds."""
    parent = list(range(len(rows)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a in enumerate(rows):
        j = i + 1
        while j < len(rows) and rows[j]["_t"] - a["_t"] <= tol:
            if rows[j]["band"] != a["band"]:
                parent[root(j)] = root(i)
            j += 1

    groups = {}
    for i in range(len(rows)):
        groups.setdefault(root(i), []).append(rows[i])
    events = [g for g in groups.values() if len({r["band"] for r in g}) > 1]
    events.sort(key=lambda g: g[0]["_t"])
    return events


def band_key(b):
    return BAND_ORDER.index(b) if b in BAND_ORDER else len(BAND_ORDER)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path, help="echoes.csv written by underdense_decay.py")
    ap.add_argument("--tolerance", type=float, default=2.0,
                    help="largest time difference between bands, s (default 2)")
    ap.add_argument("--out", type=Path,
                    help="output CSV (default: coincident_echoes.csv beside the input)")
    args = ap.parse_args()

    rows = read_echoes(args.csv)
    fields = [k for k in rows[0] if k != "_t"]
    events = find_events(rows, args.tolerance)

    out = args.out or args.csv.parent / "coincident_echoes.csv"
    combos = Counter()
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["event_id", "event_bands", "offset_s"] + fields,
                           extrasaction="ignore")
        w.writeheader()
        for n, g in enumerate(events, 1):
            bands = "+".join(sorted({r["band"] for r in g}, key=band_key))
            combos[bands] += 1
            for r in g:
                w.writerow({"event_id": n, "event_bands": bands,
                            "offset_s": round(r["_t"] - g[0]["_t"], 3), **r})

    print(f"{len(events)} events within {args.tolerance:g} s, written to {out}")
    for bands, n in sorted(combos.items()):
        print(f"  {bands}: {n}")


if __name__ == "__main__":
    main()
