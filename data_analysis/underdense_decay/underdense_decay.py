"""Find underdense meteor echoes in WSJT-X MSK144 WAV files and fit their decay times.

Each input directory holds the WAV files WSJT-X saved at one receiving station
on one band (named YYMMDD_HHMMSS.wav, UTC start of the T/R period) and that
station's ALL.TXT (any *all*.txt name). The directory name carries the station
and event, e.g. "NN4SA EM64pp PER Aug26 6m": receive callsign, receive 6-character
grid, IMO shower code, month and year, band.

For each WAV file this script:

1. Blanks impulse noise (static crashes, ignition): samples more than 5 times the
   local RMS level are zeroed. A real MSK144 echo has a near-constant envelope
   and passes through untouched. Use --blank-k 0 to turn this off.
2. Computes the full-band amplitude envelope as a short running RMS (2 ms by
   default, fine enough for 2 m echoes and Fresnel oscillations). A smoother
   10 ms version is used only to find echoes.
3. Finds echoes: bursts clearly above the noise floor, with a sharp rise and an
   exponential decay, lasting less than 2 s. Long signals (sporadic E, local
   stations, aircraft scatter, overdense trails) fail one of these tests.
   A burst counts only if WSJT-X decoded MSK144 within 0.15 s of it, because
   short noise bursts (common on 2 m) otherwise look just like 2 m echoes.
   WSJT-X prints a repeated message once per period, so a real echo carrying
   a repeat is skipped; --undecoded keeps such bursts for inspection.
4. Fits each echo with a noise-aware "plateau, then exponential decay" model and
   reports the amplitude e-folding time tau, where A(t) = A0 * exp(-t / tau)
   after the plateau. The power e-folding time is tau / 2. 2 m echoes often hold
   level for 50-100 ms before decaying; with no plateau the fit reduces to a
   plain exponential from the peak.
5. Works out the path for each echo from the decodes in ALL.TXT: transmit
   station and grid, distance and azimuth from the receiver, and the shower
   radiant's azimuth and elevation seen from the path midpoint at the echo time.
6. Plots the raw audio and the envelope, labels each echo with tau, and puts the
   path and the matching ALL.TXT decodes in the title.

Usage (from this folder, with radioconda's Python):
    python underdense_decay.py "data/NN4SA EM64pp PER Aug26 6m"
    python underdense_decay.py data/NN4SA* --max-files 100

Outputs, in --out (default <parent of the first directory>/results):
    <directory name>/<YYMMDD_HHMMSS>.png   one figure per WAV file
    echoes.csv                             one row per echo found, all directories
    tau_by_band.png                        underdense tau by band, with lambda^2 scaling
    tau_power_by_band.png                  the same for the power e-folding time tau / 2
                                           (plot_tau_by_band.py redraws both
                                           from echoes.csv)
"""

import argparse
import csv
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ephem
import matplotlib

matplotlib.use("Agg")  # write files only; no plot windows
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile
from scipy.ndimage import median_filter
from scipy.optimize import curve_fit

STAMP_RE = re.compile(r"(\d{6}_\d{6})")
CALL_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9]+(/[A-Z0-9]+)?$")
GRID4_RE = re.compile(r"^[A-R]{2}\d{2}$")
GRID6_RE = re.compile(r"^[A-R]{2}\d{2}[A-Xa-x]{2}$")

# Detection settings (dB relative to the noise floor of the file).
EDGE_DB = 2.0        # an echo starts and ends where the detection envelope crosses this
PEAK_DB = 4.0        # an echo's peak must reach at least this
MERGE_GAP_S = 0.10   # bursts closer together than this are one event
MAX_DURATION_S = 2.0 # underdense: shorter than this above EDGE_DB
MAX_RISE_S = 0.20    # sharp rise: onset to peak within this
FIT_TAIL_S = 0.30    # extra noise-floor time included after the echo in the fit
MIN_R2 = 0.6         # minimum goodness of fit (in dB, on the detection envelope)
TAU_RANGE_S = (0.002, 3.0)
MAX_PLATEAU_S = 0.15 # longest level stretch before the decay; steady signals fail the fit
DECODE_MARGIN_S = 0.15  # a decode this close to a burst confirms it carries MSK144

# Approximate radiants at shower maximum (RA, Dec in degrees, J2000), from the
# IMO Meteor Shower Calendar. Radiant drift is ignored. Codes are IMO's.
SHOWER_RADIANTS = {
    "QUA": ("Quadrantids", 230.0, 49.0),
    "LYR": ("April Lyrids", 271.0, 34.0),
    "ETA": ("Eta Aquariids", 338.0, -1.0),
    "ARI": ("Daytime Arietids", 44.0, 24.0),
    "SDA": ("Southern Delta Aquariids", 340.0, -16.0),
    "CAP": ("Alpha Capricornids", 307.0, -10.0),
    "PER": ("Perseids", 48.0, 58.0),
    "ORI": ("Orionids", 95.0, 16.0),
    "LEO": ("Leonids", 152.0, 22.0),
    "GEM": ("Geminids", 112.0, 33.0),
    "URS": ("Ursids", 217.0, 76.0),
}

BANDS = [(28.0, 29.7, "10m"), (50.0, 54.0, "6m"), (144.0, 148.0, "2m"),
         (222.0, 225.0, "1.25m"), (420.0, 450.0, "70cm")]


@dataclass
class Decode:
    utc: datetime     # time of the decoded frame (period start + DT)
    snr_db: int
    dt_s: float
    df_hz: int
    freq_mhz: float
    message: str
    tx_call: str
    tx_grid: str


@dataclass
class Station:
    call: str
    grid: str
    shower: str
    band: str


@dataclass
class Echo:
    t_start: float
    t_peak: float
    t_end: float
    peak_db: float
    rise_s: float = float("nan")
    plateau_s: float = float("nan")
    tau_s: float = float("nan")
    r2: float = float("nan")
    fit_t: np.ndarray = None
    fit_amp: np.ndarray = None
    accepted: bool = False
    reason: str = ""
    decode: Decode = None
    tx_match: str = ""


# ---------------------------------------------------------------- geography

def grid_to_latlon(grid):
    """Centre of a 4- or 6-character Maidenhead grid square, in degrees."""
    g = grid.upper()
    lon = -180 + (ord(g[0]) - 65) * 20 + int(g[2]) * 2
    lat = -90 + (ord(g[1]) - 65) * 10 + int(g[3])
    if len(g) >= 6:
        lon += (ord(g[4]) - 65) * 5 / 60 + 2.5 / 60
        lat += (ord(g[5]) - 65) * 2.5 / 60 + 1.25 / 60
    else:
        lon += 1
        lat += 0.5
    return lat, lon


def path_geometry(lat1, lon1, lat2, lon2):
    """Great-circle distance (km), azimuth from point 1 (deg), and midpoint."""
    p1, l1, p2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dl = l2 - l1
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    dist = 2 * 6371.0 * math.asin(math.sqrt(a))
    az = math.degrees(math.atan2(math.sin(dl) * math.cos(p2),
                                 math.cos(p1) * math.sin(p2)
                                 - math.sin(p1) * math.cos(p2) * math.cos(dl))) % 360
    bx = math.cos(p2) * math.cos(dl)
    by = math.cos(p2) * math.sin(dl)
    mlat = math.atan2(math.sin(p1) + math.sin(p2), math.hypot(math.cos(p1) + bx, by))
    mlon = l1 + math.atan2(by, math.cos(p1) + bx)
    return dist, az, math.degrees(mlat), (math.degrees(mlon) + 540) % 360 - 180


def radiant_azel(shower, lat, lon, utc):
    """Azimuth and elevation (deg) of a shower radiant from lat/lon at a UTC time."""
    if shower not in SHOWER_RADIANTS:
        return float("nan"), float("nan")
    _, ra, dec = SHOWER_RADIANTS[shower]
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.pressure = 0  # geometric elevation, no optical refraction
    obs.date = utc.strftime("%Y/%m/%d %H:%M:%S")
    body = ephem.FixedBody()
    body._ra, body._dec, body._epoch = math.radians(ra), math.radians(dec), ephem.J2000
    body.compute(obs)
    return math.degrees(body.az), math.degrees(body.alt)


def band_name(freq_mhz):
    for lo, hi, name in BANDS:
        if lo <= freq_mhz <= hi:
            return name
    return f"{freq_mhz:g} MHz"


# ---------------------------------------------------------------- inputs

def parse_station(dirname, args):
    """Receive call, grid, shower and band from a directory name like
    'NN4SA EM64pp PER Aug26 6m'. Command-line options override."""
    tokens = re.split(r"[\s_]+", dirname.strip())
    call = next((t.upper() for t in tokens if CALL_RE.match(t.upper())
                 and not GRID6_RE.match(t)), "")
    grid = next((t for t in tokens if GRID6_RE.match(t) or GRID4_RE.match(t.upper())), "")
    shower = next((t.upper() for t in tokens if t.upper() in SHOWER_RADIANTS), "")
    band = tokens[-1] if re.fullmatch(r"\d+(\.\d+)?c?m", tokens[-1], re.I) else ""
    return Station(args.rx_call or call, args.rx_grid or grid,
                   (args.shower or shower).upper(), band)


def parse_message(msg):
    """Return (transmitting call, its 4-char grid or '') from an MSK144 message.

    'CQ [modifier...] CALL GRID' -> CALL sent it; modifiers such as TEST, CMSH or
    a frequency like 265 are skipped. 'CALLEE CALLER ...' -> CALLER sent it.
    """
    tokens = [t.strip("<>") for t in msg.upper().split()]
    if not tokens:
        return "", ""
    if tokens[0] == "CQ":
        i = 1
        while i < len(tokens) and not CALL_RE.match(tokens[i]):
            i += 1
        if i >= len(tokens):
            return "", ""
        call, rest = tokens[i], tokens[i + 1:]
    else:
        if len(tokens) < 2 or not CALL_RE.match(tokens[1]):
            return "", ""
        call, rest = tokens[1], tokens[2:]
    grid = next((t for t in rest if GRID4_RE.match(t) and t != "RR73"), "")
    return call, grid


def read_all_txt(path, rx_call):
    """Received decodes from a WSJT-X ALL.TXT, plus a call -> grid lookup."""
    decodes, grids = [], {}
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        # stamp, freq, Rx/Tx, mode, snr, dt, df, message...
        if len(parts) < 8 or parts[2] != "Rx" or not STAMP_RE.fullmatch(parts[0]):
            continue
        try:
            stamp = datetime.strptime(parts[0], "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            snr, dt, df, freq = int(parts[4]), float(parts[5]), int(parts[6]), float(parts[1])
        except ValueError:
            continue
        msg = " ".join(parts[7:])
        call, grid = parse_message(msg)
        if not call or call == rx_call:
            continue
        if grid:
            grids[call] = grid
        decodes.append(Decode(stamp, snr, dt, df, freq, msg, call, grid))
    for d in decodes:
        d.tx_grid = d.tx_grid or grids.get(d.tx_call, "")
    return decodes


def decodes_for_file(decodes, start, duration):
    """Decodes inside one WAV file's period, with utc set to the frame time.

    WSJT-X stamps ALL.TXT lines either with the period start or with the
    second of the decode; both fall inside [start, start + duration).
    """
    out = []
    for d in decodes:
        if start <= d.utc < start + timedelta(seconds=duration):
            out.append(Decode(start + timedelta(seconds=d.dt_s), d.snr_db, d.dt_s, d.df_hz,
                              d.freq_mhz, d.message, d.tx_call, d.tx_grid))
    return out


# ---------------------------------------------------------------- signal

def blank_impulses(x, sr, k, window_s):
    """Zero samples exceeding k times the local RMS, plus a 1 ms guard each side.

    The local RMS comes from a short running median of x^2. Impulses last 1-2 ms,
    so a window several times longer ignores them but follows a real echo.
    Returns the blanked copy and the blank mask.
    """
    if k <= 0:
        return x, np.zeros(len(x), bool)
    # median of a chi-square(1) variable is 0.455 times its mean
    local_ms = median_filter(x ** 2, size=int(window_s * sr), mode="nearest") / 0.455
    bad = np.abs(x) > k * np.sqrt(np.maximum(local_ms, 1e-9))
    bad = np.convolve(bad, np.ones(int(0.002 * sr)), "same") > 0
    y = x.copy()
    y[bad] = 0
    return y, bad


def running_power(x, sr, win_s, hop_s):
    """Mean square of x in a sliding window. Returns window-centre times and power."""
    n = max(1, int(round(win_s * sr)))
    hop = max(1, int(round(hop_s * sr)))
    c = np.concatenate(([0.0], np.cumsum(x * x)))
    starts = np.arange(0, len(x) - n + 1, hop)
    return (starts + n / 2) / sr, (c[starts + n] - c[starts]) / n


def noise_floor(power, t, valid, block_s=0.1):
    """Noise power: lower quartile of 100 ms block means over the valid part.

    A quartile, not the median, so that a signal occupying most of the file
    (a local station, sporadic E) does not raise the floor.
    """
    tv, pv = t[valid], power[valid]
    blocks = np.floor((tv - tv[0]) / block_s).astype(int)
    means = np.bincount(blocks, pv) / np.maximum(np.bincount(blocks), 1)
    return np.percentile(means[np.bincount(blocks) > 0], 25)


def decay_power(t, a, tau, knee, pn):
    """Echo power holding at a until t = knee, then decaying as exp(-2(t-knee)/tau)
    (amplitude e-folding tau), plus noise power pn."""
    return a * np.exp(-2 * np.maximum(t - knee, 0) / tau) + pn


def find_echoes(t, p_fine, p_det, valid, pn, decodes, args):
    """Bursts in the file. Returns (echoes, number of bursts dropped for having
    no decode nearby)."""
    with np.errstate(divide="ignore"):  # zero padding frames give -inf, never "above"
        snr = 10 * np.log10(p_det / pn)

    above = (snr > EDGE_DB) & valid
    edges = np.diff(np.r_[0, above.astype(int), 0])
    runs = list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1))
    merged = []
    for s, e in runs:
        if merged and (t[s] - t[merged[-1][1]]) < MERGE_GAP_S:
            merged[-1][1] = e
        else:
            merged.append([s, e])

    echoes, n_undecoded = [], 0
    for s, e in merged:
        p = s + int(np.argmax(snr[s:e + 1]))
        if snr[p] < PEAK_DB:
            continue
        echo = Echo(t[s], t[p], t[e], snr[p])
        near = [d for d in decodes
                if t[s] - DECODE_MARGIN_S <= d.dt_s <= t[e] + DECODE_MARGIN_S]
        if near:
            echo.decode = min(near, key=lambda d: abs(d.dt_s - t[p]))
            echo.tx_match = "decode"
        elif args.undecoded:
            echo.tx_match = "none"
        else:
            n_undecoded += 1
            continue
        fit_echo(echo, t, p_fine, valid, p, e, pn, args)
        # rise from the last moment the signal was below the edge level, so
        # noise flickers merged in just ahead of the echo do not stretch it
        below = np.flatnonzero(snr[s:p + 1] <= EDGE_DB)
        onset = s + below[-1] if below.size else s
        duration, rise = t[e] - t[s], t[p] - t[onset]
        echo.rise_s = rise
        if s == 0 or not valid[s - 1]:
            echo.reason = "already present at start of audio (rise not seen)"
        elif duration >= MAX_DURATION_S:
            echo.reason = f"too long ({duration:.2f} s)"
        elif rise > MAX_RISE_S:
            echo.reason = f"slow rise ({rise:.2f} s)"
        elif not echo.reason:
            echo.accepted = True
        echoes.append(echo)
    return echoes, n_undecoded


def fit_echo(echo, t, p_fine, valid, p, e, pn, args):
    """Fit the decay from the true peak onward on the fine envelope.

    The detection envelope's peak can sit a few ms off the true one, so the fit
    starts at the fine envelope's maximum near it, plus half a fine window.
    """
    hop = args.hop
    half_det = int(args.detect_window / 2 / hop)
    lo, hi = max(p - half_det, 0), min(p + half_det, len(t) - 1)
    start = lo + int(np.argmax(p_fine[lo:hi + 1])) + int(args.window / 2 / hop)
    stop = min(e + int(FIT_TAIL_S / hop), len(t) - 1)
    sel = np.arange(start, stop + 1)
    sel = sel[valid[sel]]
    if sel.size < 6:
        echo.reason = "too few points to fit"
        return
    tt, y = t[sel] - t[start], p_fine[sel]
    a0 = max(np.mean(y[:3]) - pn, pn)
    # plateau guess: where the smoothed envelope first drops 1.5 dB below its peak
    k = max(1, int(args.detect_window / hop))
    ys = np.convolve(y, np.ones(k) / k, "same")
    after = np.flatnonzero(ys < ys[:max(k, 1) * 3].max() / 10 ** 0.15)
    knee0 = tt[after[0]] if after.size else 0.0
    knee_max = max(min(t[e] - t[start], MAX_PLATEAU_S), 2 * args.window)
    knee0 = min(knee0, 0.9 * knee_max)
    tau0 = max((t[e] - t[start] - knee0) / 2, 2 * args.window)

    try:
        # Two passes: weight each point by the model's own level, since the
        # scatter of a power estimate grows in proportion to the power.
        sigma = np.full_like(y, 1.0)
        for _ in range(2):
            (a, tau, knee), _ = curve_fit(
                lambda x, a, tau, knee: decay_power(x, a, tau, knee, pn),
                tt, y, p0=(a0, tau0, knee0), sigma=sigma,
                bounds=((0, TAU_RANGE_S[0], 0), (np.inf, TAU_RANGE_S[1], knee_max)))
            sigma = decay_power(tt, a, tau, knee, pn)
            a0, tau0, knee0 = a, tau, knee
    except (RuntimeError, ValueError):
        echo.reason = "fit did not converge"
        return

    # Goodness of fit in dB, with data and model both smoothed like the
    # detection envelope, so receiver noise alone does not sink R^2.
    smooth = lambda v: np.maximum(np.convolve(v, np.ones(k) / k, "valid"), 1e-12)
    yd = 10 * np.log10(smooth(y))
    md = 10 * np.log10(smooth(decay_power(tt, a, tau, knee, pn)))
    spread = np.sum((yd - yd.mean()) ** 2)
    r2 = 1 - np.sum((yd - md) ** 2) / spread if yd.size > 2 and spread > 0 else np.nan

    echo.tau_s, echo.r2, echo.plateau_s = tau, r2, knee
    echo.fit_t = t[start] + np.linspace(0, tt[-1], 300)
    echo.fit_amp = np.sqrt(decay_power(echo.fit_t - t[start], a, tau, knee, pn))
    if not r2 >= MIN_R2:
        echo.reason = f"not exponential (R2 {r2:.2f})"
    elif tau >= TAU_RANGE_S[1] * 0.99:
        echo.reason = "decay too slow"


def path_info(station, decode, utc):
    """Distance, azimuth and midpoint radiant az/el for one Rx-Tx path, or NaNs."""
    nan = float("nan")
    if not decode or not decode.tx_grid or not station.grid:
        return dict(distance_km=nan, azimuth_deg=nan, mid_lat=nan, mid_lon=nan,
                    radiant_az_deg=nan, radiant_el_deg=nan)
    rlat, rlon = grid_to_latlon(station.grid)
    tlat, tlon = grid_to_latlon(decode.tx_grid)
    dist, az, mlat, mlon = path_geometry(rlat, rlon, tlat, tlon)
    raz, rel = radiant_azel(station.shower, mlat, mlon, utc)
    return dict(distance_km=dist, azimuth_deg=az, mid_lat=mlat, mid_lon=mlon,
                radiant_az_deg=raz, radiant_el_deg=rel)


# ---------------------------------------------------------------- plots

def title_for(start, station, freq, decodes):
    head = (f"{start:%Y-%m-%d %H:%M:%S} UTC   {freq:.3f} MHz MSK144   "
            f"Rx {station.call} {station.grid}   {station.shower}")
    lines = [head]
    if not decodes:
        return head + "\n(no ALL.TXT decode in this period)"
    for call in list(dict.fromkeys(d.tx_call for d in decodes))[:3]:
        d = next(d for d in decodes if d.tx_call == call)
        g = path_info(station, d, d.utc)
        if np.isnan(g["distance_km"]):
            lines.append(f"Tx {call} (grid unknown)")
        else:
            lines.append(f"Tx {call} {d.tx_grid}: {g['distance_km']:.0f} km, "
                         f"az {g['azimuth_deg']:.0f}°   {station.shower} radiant at midpoint: "
                         f"az {g['radiant_az_deg']:.0f}°, el {g['radiant_el_deg']:.0f}°")
    for msg in list(dict.fromkeys(d.message for d in decodes))[:3]:
        ds = [d for d in decodes if d.message == msg]
        snrs = ", ".join(f"{d.snr_db:+d}" for d in ds[:6]) + (", …" if len(ds) > 6 else "")
        dts = ", ".join(f"{d.dt_s:.1f}" for d in ds[:6]) + (", …" if len(ds) > 6 else "")
        lines.append(f"{msg}   SNR {snrs} dB   DT {dts} s")
    return "\n".join(lines)


def plot_file(png, x, sr, start, station, freq, t, p_fine, p_det, pn, echoes,
              decodes, n_blanked, args):
    accepted = [e for e in echoes if e.accepted]
    zooms = accepted[:4]
    fig = plt.figure(figsize=(13, 8 if zooms else 6), constrained_layout=True)
    grid = fig.add_gridspec(2 if zooms else 1, max(len(zooms), 1),
                            height_ratios=[2.2, 1] if zooms else [1])
    ax = fig.add_subplot(grid[0, :])
    noise = math.sqrt(pn)

    ax.plot(np.arange(len(x)) / sr, x, color="0.7", lw=0.3, label="raw audio samples")
    blank_note = (f", {n_blanked / sr * 1000:.0f} ms of impulses blanked"
                  if args.blank_k > 0 else ", no blanking")
    ax.plot(t, np.sqrt(p_det), color="tab:blue", lw=1.0,
            label=f"RMS envelope, full band ({args.detect_window * 1000:.0f} ms{blank_note})")
    ax.axhline(noise, color="tab:blue", ls=":", lw=0.8, label="noise floor")

    for e in echoes:
        y = noise * 10 ** (e.peak_db / 20)
        if e.accepted:
            ax.plot(e.fit_t, e.fit_amp, color="tab:red", lw=1.6)
            ax.annotate(f"τ = {e.tau_s * 1000:.0f} ms\n{e.peak_db:.1f} dB", xy=(e.t_peak, y),
                        xytext=(8, 12), textcoords="offset points",
                        color="tab:red", fontsize=9, fontweight="bold")
        else:
            ax.annotate(f"rejected:\n{e.reason}", xy=(e.t_peak, y), xytext=(6, 8),
                        textcoords="offset points", color="0.35", fontsize=7)
    if accepted:
        ax.plot([], [], color="tab:red", lw=1.6, label="exponential fit (underdense echo)")

    ymax = np.max(np.abs(x)) * 1.05 or 1
    for d in decodes:
        ax.plot(d.dt_s, ymax * 0.97, marker="v", color="tab:green", ms=7)
    if decodes:
        ax.plot([], [], marker="v", ls="", color="tab:green", label="ALL.TXT decode time (DT)")

    ax.set_xlim(0, len(x) / sr)
    ax.set_ylim(-ymax, ymax)
    ax.set_xlabel("Time since start of file (s)")
    ax.set_ylabel("Amplitude (16-bit counts)")
    ax.set_title(title_for(start, station, freq, decodes), fontsize=9, loc="left")
    ax.legend(loc="lower left", fontsize=8, ncol=2)

    for i, e in enumerate(zooms):
        z = fig.add_subplot(grid[1, i])
        span = max(e.t_end - e.t_start, 5 * e.tau_s)
        lo, hi = e.t_start - 0.2 * span - 0.02, e.fit_t[-1] + 0.05 * span
        m = (t >= lo) & (t <= hi)
        with np.errstate(divide="ignore"):
            z.plot(t[m], 10 * np.log10(p_fine[m] / pn), color="tab:blue", lw=0.7,
                   alpha=0.6, label=f"{args.window * 1000:.0f} ms RMS")
            z.plot(t[m], 10 * np.log10(p_det[m] / pn), color="navy", lw=1.0,
                   label=f"{args.detect_window * 1000:.0f} ms RMS")
        z.plot(e.fit_t, 20 * np.log10(e.fit_amp / noise), color="tab:red", lw=1.4)
        z.axhline(0, color="tab:blue", ls=":", lw=0.8)
        z.set_xlim(lo, hi)
        tx = f", Tx {e.decode.tx_call}" if e.decode else ""
        z.set_title(f"{e.t_peak:.3f} s: τ = {e.tau_s * 1000:.1f} ms, plateau "
                    f"{e.plateau_s * 1000:.0f} ms (R² {e.r2:.2f}){tx}",
                    fontsize=8)
        z.set_xlabel("Time (s)")
        if i == 0:
            z.set_ylabel("dB above noise floor")
            z.legend(fontsize=7, loc="upper right")
        z.grid(alpha=0.3)

    fig.savefig(png, dpi=110)
    plt.close(fig)


def plot_band_summary(rows, png, power=False):
    """Underdense tau for each band, with the lambda^2 scaling of the 6 m median.

    With power=True the power e-folding time tau / 2 is plotted instead. For a
    diffusing underdense trail P(t) ~ exp(-32 pi^2 D t / lambda^2), so the power
    time is the one that gives the ambipolar diffusion coefficient,
    D = lambda^2 / (32 pi^2 tau_P). Both times scale as lambda^2, so the band
    ratios are the same either way.
    """
    scale = 0.5 if power else 1.0
    ok = [r for r in rows if r["underdense"]]
    freqs = {}
    for r in ok:
        freqs.setdefault(r["band"], []).append(r["freq_mhz"])
    if not freqs:
        return
    bands = sorted(freqs, key=lambda b: np.median(freqs[b]))
    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)
    rng = np.random.default_rng(0)
    medians = {}
    for i, b in enumerate(bands):
        tau = scale * np.array([r["tau_ms"] for r in ok if r["band"] == b])
        medians[b] = np.median(tau)
        ax.scatter(i + rng.uniform(-0.15, 0.15, tau.size), tau, s=14, alpha=0.6,
                   color="tab:blue", zorder=2)
        ax.plot([i - 0.3, i + 0.3], [medians[b]] * 2, color="black", lw=2, zorder=3)
        ax.annotate(f"median {medians[b]:.0f} ms\nn = {tau.size}", (i + 0.32, medians[b]),
                    fontsize=8, va="center")
    ref = "6m" if "6m" in medians else bands[0]
    fref = np.median(freqs[ref])
    pred = [medians[ref] * (fref / np.median(freqs[b])) ** 2 for b in bands]
    ax.plot(range(len(bands)), pred, "D--", color="tab:red", mfc="none", zorder=4,
            label=f"λ² scaling from the {ref} median")
    ax.set_yscale("log")
    ax.set_xticks(range(len(bands)), [f"{b}\n{np.median(freqs[b]):.3f} MHz" for b in bands])
    ax.set_xlim(-0.6, len(bands) - 0.1)
    if power:
        ax.set_ylabel("Power e-folding time τ_P = τ / 2 (ms)")
        ax.set_title("Underdense echo decay time by band (power)")
    else:
        ax.set_ylabel("Amplitude e-folding time τ (ms)")
        ax.set_title("Underdense echo decay time by band")
    ax.grid(alpha=0.3, which="both", axis="y")
    ax.legend(fontsize=8, loc="upper right")
    fig.savefig(png, dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- main

def process_directory(data_dir, args, out_root):
    station = parse_station(data_dir.name, args)
    all_txt = next((p for p in sorted(data_dir.iterdir())
                    if re.search(r"all.*\.txt$", p.name, re.I)), None)
    decodes = read_all_txt(all_txt, station.call) if all_txt else []
    freqs = Counter(d.freq_mhz for d in decodes if d.freq_mhz > 0)
    dir_freq = freqs.most_common(1)[0][0] if freqs else float("nan")
    out = out_root / data_dir.name
    out.mkdir(parents=True, exist_ok=True)
    print(f"\n{data_dir.name}: Rx {station.call} {station.grid}, shower {station.shower or '?'}, "
          f"{len(decodes)} decodes in {all_txt.name if all_txt else 'no ALL.TXT'}")

    wavs = sorted(data_dir.glob("*.wav"))
    if args.max_files:
        wavs = wavs[:args.max_files]
    rows, undecoded_total = [], 0
    for path in wavs:
        m = STAMP_RE.search(path.stem)
        if not m:
            print(f"  skipping {path.name}: no YYMMDD_HHMMSS in the name")
            continue
        start = datetime.strptime(m.group(1), "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        sr, x = wavfile.read(path)
        if x.ndim > 1:
            x = x[:, 0]
        x = x.astype(float)
        file_decodes = decodes_for_file(decodes, start, len(x) / sr)
        freq = Counter(d.freq_mhz for d in file_decodes).most_common(1)[0][0] \
            if file_decodes else dir_freq

        clean, blanked = blank_impulses(x, sr, args.blank_k, args.blank_window)
        t, p_fine = running_power(clean, sr, args.window, args.hop)
        p_det = np.interp(t, *running_power(clean, sr, args.detect_window, args.hop))
        nz = np.flatnonzero(x)
        first, last = (nz[0] / sr, nz[-1] / sr) if nz.size else (0, len(x) / sr)
        pad = args.detect_window / 2 + 0.01
        valid = (t > first + pad) & (t < last - pad)
        valid &= p_fine > 0  # digital silence inside a file is not noise
        if valid.sum() < len(t) / 4:
            print(f"  skipping {path.name}: mostly silent")
            continue
        pn = noise_floor(p_fine, t, valid)

        echoes, n_undecoded = find_echoes(t, p_fine, p_det, valid, pn, file_decodes, args)
        undecoded_total += n_undecoded
        plot_file(out / f"{m.group(1)}.png", x, sr, start, station, freq, t, p_fine, p_det,
                  pn, echoes, file_decodes, int(blanked.sum()), args)

        for e in echoes:
            echo_utc = start + timedelta(seconds=e.t_peak)
            d = e.decode
            geo = path_info(station, d, echo_utc)
            rows.append({
                "directory": data_dir.name, "file": path.name,
                "echo_utc": echo_utc.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "freq_mhz": freq, "band": band_name(freq) if freq == freq else station.band,
                "shower": station.shower, "rx_call": station.call, "rx_grid": station.grid,
                "tx_call": d.tx_call if d else "", "tx_grid": d.tx_grid if d else "",
                "tx_match": e.tx_match, "decode_snr_db": d.snr_db if d else "",
                **{k: round(v, 2) for k, v in geo.items()},
                "peak_time_s": round(e.t_peak, 3), "duration_s": round(e.t_end - e.t_start, 3),
                "rise_s": round(e.rise_s, 3), "peak_snr_db": round(e.peak_db, 2),
                "plateau_ms": round(e.plateau_s * 1000, 1),
                "tau_ms": round(e.tau_s * 1000, 2), "fit_r2": round(e.r2, 3),
                "underdense": e.accepted, "reason": e.reason,
            })
    n_ok = sum(r["underdense"] for r in rows)
    skipped = "" if args.undecoded else f"{undecoded_total} bursts with no decode skipped, "
    print(f"  {len(wavs)} files: {skipped}{len(rows)} decoded signals found, {n_ok} underdense")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", type=Path, nargs="+",
                    help="station/band folders, each with WAV files and an ALL.TXT")
    ap.add_argument("--out", type=Path, help="output folder (default: <parent>/results)")
    ap.add_argument("--max-files", type=int, help="process only the first N WAV files per folder")
    ap.add_argument("--window", type=float, default=0.002,
                    help="RMS window for fitting, s (default 0.002)")
    ap.add_argument("--detect-window", type=float, default=0.010,
                    help="RMS window for finding echoes, s (default 0.010)")
    ap.add_argument("--hop", type=float, default=0.001, help="envelope step, s (default 0.001)")
    ap.add_argument("--blank-k", type=float, default=5.0,
                    help="impulse blanker threshold in multiples of local RMS (0 = off)")
    ap.add_argument("--blank-window", type=float, default=0.008,
                    help="impulse blanker local-RMS window, s (default 0.008)")
    ap.add_argument("--undecoded", action="store_true",
                    help="also analyze bursts with no WSJT-X decode nearby (includes noise)")
    ap.add_argument("--rx-call", help="receive callsign, if not in the folder name")
    ap.add_argument("--rx-grid", help="receive grid square, if not in the folder name")
    ap.add_argument("--shower", help="IMO shower code, if not in the folder name")
    args = ap.parse_args()

    out_root = args.out or args.dirs[0].parent / "results"
    rows = []
    for d in args.dirs:
        if d.is_dir():
            rows += process_directory(d, args, out_root)

    if rows:
        with open(out_root / "echoes.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        plot_band_summary(rows, out_root / "tau_by_band.png")
        plot_band_summary(rows, out_root / "tau_power_by_band.png", power=True)
    print(f"\nplots, echoes.csv, tau_by_band.png and tau_power_by_band.png written to {out_root}")


if __name__ == "__main__":
    main()
