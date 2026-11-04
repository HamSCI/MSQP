# Underdense echo decay times from MSQP recordings

Finds underdense meteor echoes in the WAV files WSJT-X saves during MSK144 operation,
fits each echo's decay time, and works out the path geometry from the station's
ALL.TXT. Three companion tools read the resulting `echoes.csv`. The aim is to compare
decay times across 10 m, 6 m and 2 m against the λ² scaling of underdense theory.

Maintainer: Rob Suggs, NN4NT.

## Install

Use [radioconda](https://github.com/radioconda/radioconda-installer), which provides
numpy, scipy and matplotlib. Then add the rest:

    mamba install -c conda-forge ephem cartopy

`cartopy` is only needed for `station_map.py`.

## Input data

One folder per receiving station and band, holding that station's WSJT-X WAV files
(`YYMMDD_HHMMSS.wav`) and its ALL.TXT. Name the folder
`RXCALL GRID SHOWER MonYY BAND`, for example `NN4SA EM64pp PER Aug26 6m`. MSQP recordings
are archived on Zenodo in the HamSCI community. Put the folders under a local `data/`
folder here; git ignores it.

## Run

From this folder:

    python underdense_decay.py "data/NN4SA EM64pp PER Aug26 6m"
    python underdense_decay.py data/NN4SA*  --max-files 100

`--help` lists every option. Results go to `data/results/` (or `--out`):

- `echoes.csv`: one row per echo, with τ, plateau, SNR, the underdense test result,
  the transmit station and grid, path distance and azimuth, and the shower radiant's
  azimuth and elevation at the path midpoint.
- `<folder>/<YYMMDD_HHMMSS>.png`: audio and envelope for each WAV, with the fits.
- `tau_by_band.png` and `tau_power_by_band.png`: decay time by band, against λ².

τ is the **amplitude** e-folding time, A(t) = A₀ exp(−t/τ). The power e-folding time
used in underdense theory is τ/2, and is what `tau_power_by_band.png` plots.

## Tools for echoes.csv

| Script | Output |
|---|---|
| `plot_tau_by_band.py data/results/echoes.csv` | Redraws both decay-time-by-band plots without reprocessing the WAVs |
| `station_map.py data/results/echoes.csv` | Maps of the receive site and every transmit station heard, per band, with and without callsigns |
| `coincident_echoes.py data/results/echoes.csv` | Echoes seen within 2 s on more than one band, grouped into events |

`plot_tau_by_band.py` and `station_map.py` import functions from `underdense_decay.py`,
so keep the scripts together in this folder.
