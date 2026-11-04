"""Map the receive and transmit stations in an echoes.csv from underdense_decay.py.

For each band in the CSV this script draws two Mercator maps of the continental
US and southern Canada:

- station_map_<band>.png: the receive site, and every transmit station heard,
  coloured by whether at least one of its echoes passed the underdense test.
  A station with any underdense echo is drawn as underdense, even if it also
  produced echoes that failed.
- station_calls_<band>.png: the same map with each transmit station labelled by
  callsign. Stations in the same grid square share one label.

Transmit stations are placed at the centre of the 4-character grid square they
sent (about 1 degree of longitude by 0.5 degree of latitude), so stations in the
same square overlap. Stations that never sent a grid cannot be placed; they are
counted in the map footnote.

Usage:
    python station_map.py data/results/echoes.csv
"""

import argparse
import csv
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib

matplotlib.use("Agg")  # write files only; no plot windows
import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.lines import Line2D

from underdense_decay import grid_to_latlon

EXTENT = (-127, -60, 24, 53)  # lon west, lon east, lat south, lat north

RX_COLOR = "#eb6834"        # orange: the receive site
UNDERDENSE_COLOR = "#2a78d6"  # bold blue: at least one underdense echo
OTHER_COLOR = "#9ec5f4"     # pale blue: heard, but no underdense echo
INK = "#0b0b0b"
MUTED_INK = "#52514e"
HALO = [patheffects.withStroke(linewidth=2, foreground="white")]  # keeps labels legible


def read_stations(csv_path):
    """Per band: receive site, and each (call, grid) with its underdense flag."""
    bands = {}
    with open(csv_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            b = bands.setdefault(r["band"], {"rx": (r["rx_call"], r["rx_grid"]),
                                             "freq": r["freq_mhz"], "event": r["directory"],
                                             "tx": {}, "no_grid": set()})
            if not r["tx_grid"]:
                b["no_grid"].add(r["tx_call"])
                continue
            key = (r["tx_call"], r["tx_grid"])
            b["tx"][key] = b["tx"].get(key, False) or r["underdense"] == "True"
    for b in bands.values():
        b["no_grid"] -= {call for call, _ in b["tx"]}  # placed under another line
    return bands


def in_extent(lat, lon):
    return EXTENT[0] <= lon <= EXTENT[1] and EXTENT[2] <= lat <= EXTENT[3]


def base_map(title, footnote, scale=1.0):
    fig = plt.figure(figsize=(13 * scale, 8.5 * scale), constrained_layout=True)
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Mercator())
    ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="#eef3f8")
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#fcfcfb")
    lw = scale ** 0.5  # keep lines visible on the larger callsign maps
    ax.add_feature(cfeature.LAKES.with_scale("50m"), facecolor="#eef3f8", edgecolor="#6f777e",
                   linewidth=0.6 * lw)
    ax.add_feature(cfeature.STATES.with_scale("50m"), edgecolor="#8a8f94", linewidth=0.8 * lw)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), edgecolor="#4a4e52", linewidth=0.9 * lw)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), edgecolor="#4a4e52", linewidth=1.3 * lw)
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="#c9cdd1", alpha=0.7)
    gl.top_labels = gl.right_labels = False
    gl.xlabel_style = gl.ylabel_style = {"size": 8 * scale, "color": MUTED_INK}
    ax.set_title(title, fontsize=12 * scale, color=INK)
    fig.text(0.01, 0.005, footnote, fontsize=8 * scale, color=MUTED_INK, ha="left", va="bottom")
    return fig, ax


def draw_band(band, info, out_dir):
    rx_call, rx_grid = info["rx"]
    rx_lat, rx_lon = grid_to_latlon(rx_grid)
    placed = {}  # grid -> list of (call, underdense)
    outside = []
    for (call, grid), ud in info["tx"].items():
        lat, lon = grid_to_latlon(grid)
        if in_extent(lat, lon):
            placed.setdefault(grid, []).append((call, ud))
        else:
            outside.append(f"{call} {grid}")
    n_tx = sum(len(v) for v in placed.values()) + len(outside)
    n_ud = sum(ud for ud in info["tx"].values())

    event = info["event"].rsplit(" ", 1)[0]  # "NN4SA EM64pp PER Aug26"
    title = (f"{event} {band} ({float(info['freq']):.3f} MHz): {n_tx} transmit stations heard, "
             f"{n_ud} with underdense echoes")
    notes = ["Transmit stations are plotted at the centre of their 4-character grid square."]
    if info["no_grid"]:
        n = len(info["no_grid"])
        notes.append(f"{n} station{'s' if n > 1 else ''} never sent a grid and "
                     f"{'are' if n > 1 else 'is'} not shown: "
                     + ", ".join(sorted(info["no_grid"])) + ".")
    if outside:
        notes.append("Outside the map: " + ", ".join(sorted(outside)) + ".")
    footnote = "\n".join(notes)

    legend = [
        Line2D([], [], marker="*", ls="", ms=16, mfc=RX_COLOR, mec="white",
               label=f"Receive site {rx_call} {rx_grid}"),
        Line2D([], [], marker="o", ls="", ms=8, mfc=UNDERDENSE_COLOR, mec="white",
               label="Transmit station with underdense echoes"),
        Line2D([], [], marker="o", ls="", ms=8, mfc=OTHER_COLOR, mec="white",
               label="Transmit station, no underdense echoes"),
    ]

    for labelled in (False, True):
        # The callsign map is drawn larger so stacked labels fit between grid squares.
        scale = 2.2 if labelled else 1.0
        fig, ax = base_map(title, footnote, scale)
        # Draw pale markers first so underdense stations sit on top.
        for ud_pass in (False, True):
            for grid, stations in placed.items():
                if any(ud for _, ud in stations) != ud_pass:
                    continue
                lat, lon = grid_to_latlon(grid)
                ax.plot(lon, lat, "o", ms=6 if labelled else 9,
                        mfc=UNDERDENSE_COLOR if ud_pass else OTHER_COLOR, mec="white",
                        mew=1, transform=ccrs.PlateCarree(), zorder=3 + ud_pass)
                if labelled:
                    stations.sort(key=lambda s: (not s[1], s[0]))
                    # Up to 4 callsigns in one column; more go in two, centred on the square.
                    cols = 1 if len(stations) <= 4 else 2
                    rows = -(-len(stations) // cols)
                    top = 3.5 * (rows - 1)
                    for i, (call, ud) in enumerate(stations):
                        ax.annotate(call, (lon, lat), xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
                                    xytext=(5 + 28 * (i % cols), top - 7 * (i // cols)),
                                    textcoords="offset points", path_effects=HALO,
                                    fontsize=6, va="center",
                                    color=INK if ud else MUTED_INK,
                                    fontweight="bold" if ud else "normal", zorder=6)
        ax.plot(rx_lon, rx_lat, "*", ms=20, mfc=RX_COLOR, mec="white", mew=1,
                transform=ccrs.PlateCarree(), zorder=5)  # under the callsigns
        if labelled:
            ax.annotate(rx_call, (rx_lon, rx_lat), xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
                        xytext=(-10, 0), textcoords="offset points", fontsize=9,
                        fontweight="bold", ha="right", va="center", path_effects=HALO, color=INK, zorder=7)
            legend[1].set_label("Underdense echoes (bold callsign)")
            legend[2].set_label("No underdense echoes (grey callsign)")
        ax.legend(handles=legend, loc="lower left", fontsize=9 * scale, markerscale=scale ** 0.5,
                  framealpha=0.95)
        name = f"station_calls_{band}.png" if labelled else f"station_map_{band}.png"
        fig.savefig(out_dir / name, dpi=150)
        plt.close(fig)
        print(f"  {name}: {n_tx} stations, {n_ud} underdense")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path, help="echoes.csv written by underdense_decay.py")
    ap.add_argument("--out", type=Path, help="output folder (default: <csv folder>/maps)")
    args = ap.parse_args()

    out_dir = args.out or args.csv.parent / "maps"
    out_dir.mkdir(parents=True, exist_ok=True)
    for band, info in read_stations(args.csv).items():
        draw_band(band, info, out_dir)
    print(f"\nmaps written to {out_dir}")


if __name__ == "__main__":
    main()
