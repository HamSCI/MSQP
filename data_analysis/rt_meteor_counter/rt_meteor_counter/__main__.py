"""Start the meteor counter.

    python -m rt_meteor_counter                 open the GUI
    python -m rt_meteor_counter --wav FILE      process a recording without the GUI
"""

import argparse
from collections import Counter
from pathlib import Path

from .config import AUDIO_OFFSET_HZ, PILOT_MHZ, THRESHOLD_DB

DEFAULT_OUT = Path.home() / "RT_meteor_counter_data"


def run_file(args):
    from .detector import MeteorDetector
    from .output import MeteorLog
    from .sources import WavSource, parse_utc

    start = parse_utc(args.start_utc) if args.start_utc else None
    source = WavSource(args.wav, realtime=False, start_utc=start)
    detector = MeteorDetector(threshold_db=args.threshold)
    if args.mhz:
        channel, dial = None, args.mhz * 1e6 - AUDIO_OFFSET_HZ
    else:
        channel, dial = args.channel, PILOT_MHZ[args.channel] * 1e6 - AUDIO_OFFSET_HZ
    log = MeteorLog(args.out, channel, dial, live=False)
    source.start()
    reasons = Counter()
    while True:
        try:
            t, audio = source.read()
        except EOFError:
            break
        for m in detector.process(audio, t)[2]:
            log.add(m)
            reasons["underdense" if m.accepted else m.reason.split(" (")[0]] += 1
    log.close()
    print(f"{reasons['underdense']} underdense meteors; written to {args.out}")
    for r, n in reasons.most_common():
        if r != "underdense":
            print(f"  rejected, {r}: {n}")


def main():
    ap = argparse.ArgumentParser(prog="rt_meteor_counter", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wav", help="process this recording as fast as possible, without the GUI")
    ap.add_argument("--start-utc", help="UTC of the recording's first sample, "
                                        "e.g. 2026-11-01T03:00:00 (default: now)")
    ap.add_argument("--channel", type=int, choices=sorted(PILOT_MHZ), default=2,
                    help="TV channel, for the log (default 2)")
    ap.add_argument("--mhz", type=float,
                    help="the carrier's frequency in MHz, for the log, instead of a TV channel "
                         "(receiver tuned 1 kHz below it in USB)")
    ap.add_argument("--threshold", type=float, default=THRESHOLD_DB,
                    help=f"dB above each bin's floor (default {THRESHOLD_DB:g})")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help=f"output folder (default {DEFAULT_OUT})")
    args = ap.parse_args()
    if args.wav:
        run_file(args)
    else:
        from .gui import run
        run(args.out)


if __name__ == "__main__":
    main()
