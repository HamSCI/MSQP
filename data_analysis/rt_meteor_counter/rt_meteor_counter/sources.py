"""Signal sources. Each delivers blocks of 8 kHz audio with the UTC time of the
block's first sample.

- SdrSource: any receiver SoapySDR can open (RTL-SDR, and SDRplay once its
  SoapySDR module is installed). Tunes in USB 1 kHz below the DTV pilot.
- SoundcardSource: audio from an external receiver into the PC's sound card.
- WavSource: a recording, for testing and reprocessing.
"""

import math
import queue
import time
from datetime import datetime, timezone

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

from .config import AUDIO_RATE
from .dsp import AudioDecimator, SdrToAudio

BLOCK_S = 0.1

# SDR sample rates to try, in order; each must be a multiple of 8 kHz.
# 240 kHz suits the RTL-SDR (valid 225-300 kHz); SDRplay needs 2 MHz or more.
SDR_RATES = [240000, 256000, 288000, 2048000, 2000000, 1024000, 960000]
TUNE_OFFSET_HZ = 60000  # tune this far below the dial frequency, away from the DC spike
# SoapySDR drivers offered as inputs (sdrplay once SoapySDRPlay3 is installed).
SDR_DRIVERS = ["rtlsdr", "sdrplay", "airspy", "airspyhf", "hackrf", "lime", "bladerf",
               "plutosdr", "uhd"]


def list_sdrs():
    """[(label, device args)] for every receiver SoapySDR can see."""
    try:
        import SoapySDR
    except ImportError:
        return []
    # Some SoapySDR modules in radioconda serve hardware with extra drivers (UHD
    # etc.) and complain loudly when those are absent; that is harmless here.
    SoapySDR.setLogLevel(SoapySDR.SOAPY_SDR_CRITICAL)
    found = []
    # Ask each SDR driver separately. A search across all drivers also runs
    # radioconda's SoapyAudio and network modules, which on Windows can leave the
    # RTL-SDR unopenable or abort the program (SoapyAudio's Hamlib).
    for driver in SDR_DRIVERS:
        try:
            results = SoapySDR.Device.enumerate({"driver": driver})
        except Exception:
            continue
        for kw in results:
            args = {k: kw[k] for k in kw.keys()}
            label = args.get("label") or driver
            found.append((f"SDR: {label}", args))
    return found


def list_audio_devices(kind):
    """[(label, index)] of sound-card inputs ("input") or outputs ("output")."""
    import sounddevice as sd
    api = sd.default.hostapi
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    return [(d["name"], i) for i, d in enumerate(sd.query_devices())
            if d["hostapi"] == api and d[key] > 0]


class SdrSource:
    def __init__(self, args, dial_hz, gain_db=30.0, ppm=0.0):
        self.args, self.dial_hz, self.gain_db, self.ppm = args, dial_hz, gain_db, ppm
        self.dev = self.stream = None
        self.overflows = 0
        self.description = f"{args.get('driver', 'SDR')} at {dial_hz / 1e6:.6f} MHz USB"

    def start(self):
        import SoapySDR
        from SoapySDR import SOAPY_SDR_CF32, SOAPY_SDR_RX
        # A plain dict loses its "driver" key on the way into radioconda's
        # SoapySDR, which then searches every module (see list_sdrs).
        kwargs = SoapySDR.SoapySDRKwargs()
        for k, v in self.args.items():
            kwargs[k] = v
        self.dev = SoapySDR.Device(kwargs)
        rate = self._pick_rate()
        self.rate = rate
        self.dev.setSampleRate(SOAPY_SDR_RX, 0, rate)
        offset = min(TUNE_OFFSET_HZ, rate / 4)
        if self.ppm and self.dev.hasFrequencyCorrection(SOAPY_SDR_RX, 0):
            self.dev.setFrequencyCorrection(SOAPY_SDR_RX, 0, self.ppm)
        self.dev.setFrequency(SOAPY_SDR_RX, 0, self.dial_hz - offset)
        if self.dev.hasGainMode(SOAPY_SDR_RX, 0):
            self.dev.setGainMode(SOAPY_SDR_RX, 0, False)  # no AGC: decay times need fixed gain
        self.dev.setGain(SOAPY_SDR_RX, 0, self.gain_db)
        self.convert = SdrToAudio(rate, offset)
        self.buf = np.empty(int(rate * BLOCK_S), np.complex64)
        self.stream = self.dev.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
        self.dev.activateStream(self.stream)

    def _pick_rate(self):
        from SoapySDR import SOAPY_SDR_RX
        listed = set(int(r) for r in self.dev.listSampleRates(SOAPY_SDR_RX, 0))
        ranges = [(r.minimum(), r.maximum()) for r in self.dev.getSampleRateRange(SOAPY_SDR_RX, 0)]
        for r in SDR_RATES:
            if r in listed or any(lo <= r <= hi for lo, hi in ranges):
                return r
        usable = sorted(r for r in listed if r % AUDIO_RATE == 0 and r >= 200000)
        if usable:
            return usable[0]
        raise RuntimeError("this SDR offers no sample rate that is a multiple of 8 kHz")

    def read(self, timeout=0.5):
        from SoapySDR import SOAPY_SDR_OVERFLOW, SOAPY_SDR_TIMEOUT
        n = 0
        while n < len(self.buf):
            sr = self.dev.readStream(self.stream, [self.buf[n:]], len(self.buf) - n,
                                     timeoutUs=int(1e6))
            if sr.ret > 0:
                n += sr.ret
            elif sr.ret == SOAPY_SDR_OVERFLOW:
                self.overflows += 1
            elif sr.ret != SOAPY_SDR_TIMEOUT:
                raise RuntimeError(f"SDR read error {sr.ret}")
        t_first = time.time() - n / self.rate
        return t_first, self.convert(self.buf[:n].copy())

    def stop(self):
        if self.dev is not None and self.stream is not None:
            try:
                self.dev.deactivateStream(self.stream)
                self.dev.closeStream(self.stream)
            except Exception:
                pass
        self.dev = self.stream = None


class SoundcardSource:
    RATES = [48000, 16000, 8000, 96000, 24000, 32000]

    def __init__(self, device):
        self.device = device
        self.overflows = 0
        self.description = "sound card"

    def start(self):
        import sounddevice as sd
        for rate in self.RATES:
            try:
                sd.check_input_settings(device=self.device, samplerate=rate, channels=1)
                break
            except Exception:
                continue
        else:
            raise RuntimeError("the sound card offers no rate that is a multiple of 8 kHz")
        self.rate = rate
        self.convert = AudioDecimator(rate)
        self.q = queue.Queue(maxsize=200)
        self.stream = sd.InputStream(device=self.device, samplerate=rate, channels=1,
                                     dtype="float32", blocksize=int(rate * BLOCK_S),
                                     callback=self._callback)
        self.stream.start()

    def _callback(self, indata, frames, time_info, status):
        if status:
            self.overflows += 1
        try:
            self.q.put_nowait((time.time() - frames / self.rate, indata[:, 0].copy()))
        except queue.Full:
            self.overflows += 1

    def read(self, timeout=0.5):
        try:
            t, x = self.q.get(timeout=timeout)
        except queue.Empty:
            return None
        return t, self.convert(x)

    def stop(self):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass


class WavSource:
    """A WAV file, played in real time (GUI) or as fast as possible (batch)."""

    def __init__(self, path, realtime=True, start_utc=None):
        self.path, self.realtime, self.start_utc = path, realtime, start_utc
        self.overflows = 0
        self.description = f"file {path}"

    def start(self):
        rate, data = wavfile.read(self.path)
        if data.ndim > 1:
            data = data[:, 0]
        if data.dtype.kind == "i":
            data = data / float(np.iinfo(data.dtype).max)
        elif data.dtype.kind == "u":
            data = (data - 128) / 128.0
        data = data.astype(np.float32)
        if rate % AUDIO_RATE == 0:
            data = AudioDecimator(rate)(data)
        else:
            g = math.gcd(rate, AUDIO_RATE)
            data = resample_poly(data, AUDIO_RATE // g, rate // g).astype(np.float32)
        self.audio = data
        self.pos = 0
        self.t0 = self.start_utc.timestamp() if self.start_utc else time.time()
        self.wall0 = time.time()

    def read(self, timeout=0.5):
        if self.pos >= len(self.audio):
            raise EOFError
        n = int(BLOCK_S * AUDIO_RATE)
        if self.realtime:
            wait = self.wall0 + (self.pos + n) / AUDIO_RATE - time.time()
            if wait > 0:
                time.sleep(wait)
        block = self.audio[self.pos:self.pos + n]
        t = self.t0 + self.pos / AUDIO_RATE
        self.pos += n
        return t, block

    def stop(self):
        pass


def parse_utc(text):
    """'2026-11-01T03:00:00' (UTC) -> aware datetime."""
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
