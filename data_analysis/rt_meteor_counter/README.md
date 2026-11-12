# RT Meteor Counter

Counts underdense meteors in real time using forward scatter of the pilot carriers of
digital TV (ATSC) stations on VHF-low channels 2–6. For each meteor it logs the UTC time,
audio frequency (which identifies the transmitter), peak amplitude and decay time. It
shows a waterfall with a marker on each meteor, beeps at the meteor's frequency, and
builds a chart of meteors per 15 minutes over the last 24 hours. It can also watch a
beacon or meteor radar carrier on any frequency you type in.

It reads from an RTL-SDR, from any other receiver SoapySDR supports, or from a receiver's
audio through the PC sound card. It runs on Windows, Linux and macOS with the
[radioconda](https://github.com/radioconda/radioconda-installer) Python distribution.

## How it works

The receiver is tuned in upper sideband 1 kHz below the pilot, so each station's pilot
lands near 1000 Hz in the audio.

The ATSC pilot is 309.441 kHz above the channel's lower edge.

| Channel | Pilot (MHz) | Dial, USB (MHz) |
|---|---|---|
| 2 | 54.309441 | 54.308441 |
| 3 | 60.309441 | 60.308441 |
| 4 | 66.309441 | 66.308441 |
| 5 | 76.309441 | 76.308441 |
| 6 | 82.309441 | 82.308441 |

Individual stations may sit tens of Hz off the nominal pilot, so their carriers spread
around 1000 Hz.

1. **Audio.** An SDR is tuned 60 kHz below the dial frequency to avoid its zero-frequency
   spike. The signal is shifted to the dial frequency and decimated to 8 kHz, and only the
   upper sideband is kept (the lower sideband is suppressed by about 80 dB). Sound-card
   input is decimated to the same 8 kHz. Everything after this point is the same for both.
2. **Impulse blanking.** Samples more than 5 times the local RMS are zeroed, as in the MSQP
   MSK144 echo analysis.
3. **Finding echoes.** 1024-point FFTs every 16 ms give 7.8 Hz bins from 500 to 1500 Hz.
   Each bin keeps its own noise floor, the median of its power over the last minute. A bin
   carrying a steady direct-path carrier therefore has a high floor, and only a rise above
   the carrier counts. An echo must rise 10 dB above its bin's floor (adjustable).
   Neighbouring bins that light up together are treated as one meteor. A burst covering
   much of the band at once is impulse noise and is dropped.
4. **Measuring the decay.** The FFT window spans 128 ms, too long to time a 60 ms decay
   (typical at channel 6). For each meteor, the audio around the detected frequency is
   therefore filtered to ±25 Hz and its envelope sampled every 4 ms. If another station's
   carrier is nearby, the filter narrows to half the distance to that carrier. The
   envelope is fitted with the same model as the MSK144 analysis: a level plateau of up to
   150 ms, then an exponential decay, plus noise.
5. **Underdense test.** An echo counts as an underdense meteor if it:
   - lasts under 2 s
   - rises within 0.2 s
   - fits the model with R² ≥ 0.3
   - has an integrated SNR of at least 0.8 s

   **Integrated SNR** is the echo's power above the noise, in units of the noise power,
   summed over the echo. It is the test that separates real echoes from noise flickers,
   which can fit a short decay well but carry little energy.

**Decay time τ** is the amplitude e-folding time: A(t) = A₀·exp(−t/τ) after the plateau.
The power decays with τ/2.

### Time resolution

| Quantity | Resolution |
|---|---|
| Detection spectra | one every 16 ms, each spanning 128 ms, with 7.8 Hz bins |
| Envelope for the decay fit | sampled every 4 ms |
| Envelope filter response (10–90% rise in power) | 15 ms at ±25 Hz; 30 ms at ±12 Hz; 60 ms at ±6 Hz (the narrowest, used only beside a close carrier) |
| Time stamp of an echo's peak | 4 ms in the envelope. The absolute time is only as good as the PC clock, which should be NTP-synchronized. |

On synthetic echoes at 26 dB peak SNR, with the ±25 Hz filter, the decay time τ is
measured:
- within about ±15% from 40 ms upward
- with up to about ±40% scatter for 16–25 ms
- not reliably below about 12 ms

Echoes that short are also often missed, because they fill only a small part of the
128 ms FFT window.

### Why a 1024-point FFT

Computing power isn't the limit: this runs at about 7% of one CPU core. The limit is
physics. A finer frequency bin needs a longer time window, and 7.8 Hz bins need 128 ms.
That is fine for finding echoes and telling stations tens of Hz apart, but too coarse for
timing a short decay. That is why the decay is measured on the narrow-band envelope
instead (step 4).

## Tested so far, on synthetic data

`tools/make_test_signal.py` writes a recording with known content:
- noise and impulse noise
- a fading direct-path carrier
- echoes from five transmitters 22–92 Hz apart, one on the carrier's own frequency
- long, overdense-like echoes

`tools/check_detections.py` scores the output against that truth table. On a 10-minute test:

| Envelope SNR of echo | Found |
|---|---|
| 5–10 dB | 5 of 19 |
| 10–15 dB | 10 of 19 |
| 15–20 dB | 12 of 19 |
| 20–26 dB | 16 of 19 |

- **Decay time:** fitted/true median 0.94; half of all echoes fall within 0.81–1.05.
  Accuracy is the same from 20 to 500 ms.
- **Frequency:** within 1.3 Hz rms.
- **False alarms:** none in 10 minutes of noise and carrier only; one in the 10-minute
  test file.
- **Long echoes:** all rejected.

**Known limit: echoes on the same frequency as a strong direct-path carrier are not
measured.** These are echoes from the transmitter you also hear directly. The echo and the
carrier beat together, and no filter can separate them.

The detection settings were tuned on synthetic data only. Real signals will differ, so
expect to revisit `rt_meteor_counter/config.py` after the first nights of real data. The
rejects file (below) is there to help with that.

## Installing

1. Install [radioconda](https://github.com/radioconda/radioconda-installer). It includes
   SoapySDR with the RTL-SDR driver, PyQt5 and pyqtgraph.
2. In the **Radioconda Prompt**, add the sound-card library:

   ```
   mamba install -c conda-forge python-sounddevice
   ```
3. Copy or clone this folder to the PC.

To run it, use the Radioconda Prompt:

```
cd RT_meteor_counter
python -m rt_meteor_counter
```

Or double-click `run_meteor_counter.bat`, which assumes radioconda is in its default place,
`%USERPROFILE%\radioconda`.

## Receiver drivers

### RTL-SDR (Windows)
1. Download **Zadig** from https://zadig.akeo.ie and plug in the RTL-SDR.
2. In Zadig, choose *Options → List All Devices*, then select **Bulk-In, Interface
   (Interface 0)**. It may instead appear as RTL2838UHIDIR or "RTL2832U".
3. Set the driver to **WinUSB** and press *Replace Driver*.

This is needed once per dongle. Don't change the driver of any other device in the list.
To check the result, run `rtl_test` in the Radioconda Prompt; it should find the dongle.

Radioconda's RTL-SDR library is osmocom's. An RTL-SDR Blog **V4** may need RTL-SDR Blog's
own build of the library. Try the V4 first, and check that the waterfall shows the
expected pilots.

### SDRplay RSP2pro
- **SDRplay API 3.x** (from sdrplay.com) is required. It runs as a Windows service, and
  every program other than SDRplay's own uses it.
- **The ExtIO DLL is not needed.** It is a plug-in for ExtIO host programs such as HDSDR,
  and Python can't use it.
- **Python needs the SoapySDR module for SDRplay ("SoapySDRPlay3").** It isn't in
  radioconda for Windows, so for now there are two routes:
  - **Now:** run SDRconnect or SDRuno in USB on the dial frequency, with **AGC off**. Send
    its audio through a virtual audio cable (e.g. VB-Audio Cable), and choose that cable
    as the *Sound card* input here.
  - **Later:** build the SoapySDRPlay3 module against radioconda's SoapySDR. Once it's
    installed, the RSP appears in the *Input* list automatically, with no change to this
    program.

### Sound card from an external receiver
Tune the receiver to the dial frequency in USB with **AGC off**, so that decay times are
real. Connect its audio to the sound card's line input.

### Frequency accuracy
At 54–82 MHz an SDR's crystal error dominates: 1 ppm is 54–82 Hz, as much as the spread
between stations. Use *SDR correction (ppm)* to put a known strong local pilot where it
belongs in the audio. The `rf_mhz` column in the log is only as accurate as this setting.

## Using it

- **Input:** an SDR, a sound-card input, or a WAV recording (played in real time).
- **Signal:** one of TV channels 2–6, chosen by where the stations lie relative to you, or
  **Other frequency** for any carrier you type in MHz, such as a beacon or a CW meteor
  radar. For a typed frequency the receiver is tuned 1 kHz below it in USB (an SDR is
  tuned that way automatically; set an external receiver to the dial frequency shown),
  so the carrier lands near 1000 Hz. The detector searches 500–1500 Hz around it. The
  decay tests were tuned for 54–82 MHz, so check the first results on other bands.
- **SDR gain:** fixed (the SDR's AGC is turned off). Raise it until the noise floor rises
  in the waterfall, but not so far that strong local signals overload.
- **Audio output:** where to play the received audio, or (none). The speaker level is set
  automatically; this never alters the audio that's analysed. The beep plays at each
  meteor's audio frequency, 0.5 s after the meteor is detected, so you hear the echo
  itself first.
- **Threshold:** how many dB an echo must rise above its own bin's floor (default 10).
  Lower thresholds work down to 6 dB, but they let through many more noise flickers to
  check (about 2,000 a minute at 6 dB), so the processing load rises to about 15% of one
  core.
- **Waterfall sliders:**
  - **Speed:** how fast the display scrolls. Changing it clears the display.
  - **Sensitivity:** the black level.
  - **Contrast:** the dB range from black to white.
- **Markers:** cyan rings mark accepted meteors on the waterfall.
- **Warm-up:** detection starts 15 s after Start, once each bin's floor has settled.
- **Count plot:** meteors per 15 minutes over the last 24 hours, sliding so the right edge
  is always now, to show the daily cycle. Yesterday's part comes from yesterday's meteors
  file, so it survives a restart. Tick **Count plot in local time** to label the hours in
  the PC's time zone, e.g. for visitors; the files stay in UTC.
- **Saved settings:** everything in the window (input, signal, gains, audio, threshold,
  sliders, output folder, window size) is saved when you close the program or press
  Start, and restored at the next start. Devices are remembered by name. If one is
  missing, choose again.

## Output files

Written to the output folder (default `%USERPROFILE%\RT_meteor_counter_data`), one set per
UTC day:

| File | Contents |
|---|---|
| `meteors_YYYYMMDD.csv` | every underdense meteor |
| `rejects_YYYYMMDD.csv` | echoes that failed a test, with the reason. Noise flickers that fail the integrated-SNR test aren't written. |
| `counts_YYYYMMDD.csv` | meteors per 15-minute bin |
| `counts_YYYYMMDD.png` | the 15-minute chart. Saved once the UTC day has ended, or when you press Stop or close the program. |
| `clips_YYYYMMDD/` | audio of every logged meteor and reject (not impulse noise), from 2 s before the peak to 2.5 s after, as 32-bit float WAV, e.g. `184313.244_1065Hz_reject.wav` |

To see why an echo was accepted or rejected, plot its clip:

```
python tools/plot_clip.py %USERPROFILE%\RT_meteor_counter_data\clips_20261103\101502.120_1043Hz_reject.wav
```

This saves a `.png` beside the clip. The top panel is the spectrogram around the echo. The
bottom panel is the envelope the detector fitted, with the fitted decay drawn over it.

Restarting during the day reloads that day's counts from the meteors file.

Meteor columns:

| Column | Meaning |
|---|---|
| `utc` | time of the echo's peak (from the PC clock; keep it synchronised) |
| `audio_hz` | the echo's audio frequency, which identifies the transmitter |
| `peak_snr_db` | peak power above the noise just before the echo, in the envelope filter |
| `tau_ms` | amplitude e-folding time |
| `rf_mhz` | dial frequency + audio frequency |
| `channel` | TV channel; blank for a typed frequency |
| `peak_dbfs`, `noise_dbfs` | absolute levels; 0 dBFS is a full-scale sine |
| `bin_snr_db` | peak in the FFT bin, above that bin's floor |
| `plateau_ms`, `rise_ms`, `duration_s` | echo shape |
| `fit_r2`, `integrated_snr_s` | the fit-quality tests |
| `env_bw_hz` | half-width of the envelope filter used for the fit (narrower beside a steady carrier). Files started by the first version lack this column. |

## Processing a recording without the GUI

```
python -m rt_meteor_counter --wav night.wav --start-utc 2026-12-14T03:00:00 --channel 3 --out results
```

For another carrier, give its frequency instead of a channel, e.g. `--mhz 50.260`. Either
one only labels the log; the recording is analysed the same way.

This runs about 15 times faster than real time.

## Testing

```
python tools/make_test_signal.py test.wav --minutes 10
python -m rt_meteor_counter --wav test.wav --start-utc 2026-01-01T00:00:00 --out test_out
python tools/check_detections.py test_truth.csv test_out 2026-01-01T00:00:00
```

## Origin

The echo tests and decay model come from the MSQP MSK144 underdense-echo analysis in
`../underdense_decay` in this repository. The program follows Rob Suggs
(NN4NT)'s Fortran and C meteor counter from the early 2000s.
