"""Write a synthetic 8 kHz recording with known meteors, for testing the detector.

Contents:
- white noise
- a direct-path carrier at 1010 Hz with slow fading
- underdense echoes at five "transmitter" frequencies (one of them on the
  carrier), with random strength, plateau and decay time
- a few long, fluctuating echoes (overdense-like), which should be rejected
- impulse noise, which should be blanked or rejected

The truth table goes beside the WAV file as <name>_truth.csv. Signal strength
is given as the SNR in the detector's +-25 Hz envelope filter.

    python tools/make_test_signal.py test.wav --minutes 10
    python tools/make_test_signal.py noise.wav --minutes 10 --no-meteors
"""

import argparse
import csv

import numpy as np
from scipy.io import wavfile

RATE = 8000
NOISE_RMS = 0.01
TX_HZ = [950.0, 987.5, 1010.0, 1043.0, 1102.0]
CARRIER_HZ = 1010.0


def env_snr_to_amp(snr_db):
    # In the detector's envelope, white noise of rms s gives power s^2/40 and a
    # sine of amplitude A gives A^2.
    return np.sqrt(NOISE_RMS ** 2 / 40 * 10 ** (snr_db / 10))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--no-meteors", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    n = int(args.minutes * 60 * RATE)
    t = np.arange(n) / RATE
    x = rng.normal(0, NOISE_RMS, n)
    fade = 1 + 0.5 * np.sin(2 * np.pi * t / 40)
    x += env_snr_to_amp(25) * fade * np.sin(2 * np.pi * CARRIER_HZ * t)

    truth = []
    if not args.no_meteors:
        tm = 20.0   # leave the detector's warm-up alone
        while True:
            tm += rng.exponential(6.0) + 1.0
            if tm > args.minutes * 60 - 5:
                break
            f = rng.choice(TX_HZ) + rng.uniform(-2, 2)
            snr = rng.uniform(5, 25)
            amp = env_snr_to_amp(snr)
            if rng.random() < 0.08:   # long, fluctuating, overdense-like
                dur = rng.uniform(3, 8)
                k = np.arange(int(dur * RATE))
                shape = (1 + 0.6 * np.sin(2 * np.pi * k / RATE / rng.uniform(0.5, 2))) / 1.6
                shape *= np.minimum(k / (0.05 * RATE), 1)
                kind, tau, plateau = "long", np.nan, np.nan
            else:
                tau = float(np.exp(rng.uniform(np.log(0.02), np.log(0.5))))
                plateau = float(rng.choice([0.0, rng.uniform(0.02, 0.12)]))
                rise = rng.uniform(0.003, 0.02)
                k = np.arange(int((rise + plateau + 8 * tau) * RATE))
                tk = k / RATE
                shape = np.where(tk < rise, tk / rise,
                                 np.exp(-np.maximum(tk - rise - plateau, 0) / tau))
                kind = "underdense"
            i0 = int(tm * RATE)
            k = k[: n - i0]
            seg = amp * shape[: len(k)] * np.sin(2 * np.pi * f * (i0 + k) / RATE
                                                 + rng.uniform(0, 2 * np.pi))
            x[i0:i0 + len(k)] += seg
            peak_t = tm + (np.argmax(shape) / RATE)
            truth.append(dict(t_s=round(peak_t, 3), audio_hz=round(f, 2), snr_db=round(snr, 1),
                              tau_ms=round(1000 * tau, 1), plateau_ms=round(1000 * plateau, 0),
                              kind=kind, on_carrier=abs(f - CARRIER_HZ) < 5))

    # impulse noise: 1-2 ms spikes, about one per second
    for ti in rng.uniform(0, args.minutes * 60, int(args.minutes * 60)):
        i = int(ti * RATE)
        m = rng.integers(8, 16)
        x[i:i + m] += rng.normal(0, 0.3, len(x[i:i + m]))

    wavfile.write(args.wav, RATE, x.astype(np.float32))
    if truth:
        with open(args.wav.rsplit(".", 1)[0] + "_truth.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(truth[0]))
            w.writeheader()
            w.writerows(truth)
    print(f"{args.wav}: {args.minutes:g} min, {len(truth)} echoes "
          f"({sum(r['kind'] == 'underdense' for r in truth)} underdense)")


if __name__ == "__main__":
    main()
