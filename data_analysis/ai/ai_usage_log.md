# AI Usage Log — MSQP data analysis

This log records all substantive AI-assisted sessions for the code in `data_analysis/` of
`HamSCI/MSQP`.

Required per University of Scranton AI Policy, HamSCI Generative AI Use Agreement, NASA AI guidance, NSF AI guidance, and the project-specific expectations in `.claude/rules/ai-governance.md`.

The first two entries are carried over from the AI usage log of `HamSCI/msqp.hamsci.org`, where `underdense_decay.py` started out as `analysis/underdense_decay.py`. Their git hashes refer to that repository; bf1bf72 is a local commit that was never pushed.

---

<!-- Append new entries below this line, newest at the bottom. Use the format produced by the /commit command. -->

## [2026-10-27 14:38 CDT]
- **Tool**: Claude (Anthropic), claude-opus-5-5
- **Session Purpose**: Rob Suggs (NN4NT) asked for a tool to analyze WSJT-X MSK144 WAV recordings from the MSQP: plot raw audio and a 72 ms FFT-filtered (500–2800 Hz) amplitude envelope for each file, title each plot with the matching ALL.TXT decodes, and fit the e-folding time of each underdense meteor echo; also to judge whether the FFT filtering is worth running on the full dataset. Earlier in the session: installed radioconda 2025.03.14 (Python 3.12, GNU Radio 3.10) locally and reviewed ephem for shower-radiant az/el (not committed).
- **Sections/Files Affected**: new `analysis/underdense_decay.py`; new `requirements.txt`; `.gitignore` (adds `data/` so participant logs, recordings and derived plots stay local).
- **Nature of Contribution**: Code generation and data analysis.
- **Human Review Status**: Partially reviewed. Rob reviewed all six output plots, listened to 260812_022800.wav, and confirmed the Fresnel-oscillation interpretation of decay ripple; the code itself has not been reviewed line by line.
- **Verification**:
  - Ran on six files from the 2026-08-12 Perseids MSQP (one station's ALL.TXT); 7 echoes fitted, τ = 87–271 ms (amplitude e-folding; power τ/2).
  - Found impulse noise producing false echoes in 2 files; added a 5× local-RMS blanker (≈0.05% of samples). Both false detections removed; real echoes kept 6–12 dB.
  - Filter vs. no filter: receivers already band-limit above ~3 kHz, so the filter gains ~1 dB. Unfiltered run gave one false echo and missed one decoded echo.
  - 260812_020130 (decode at −5 dB) has no echo measurable in amplitude; no τ forced.
  - 260812_022800 decay ripple is Fresnel oscillation per NN4NT (meteor-speed analysis deferred).
  - Detection thresholds (4 dB peak, 0.2 s rise, 2 s duration, R² ≥ 0.6) were tuned on these six files only; to be reviewed before bulk processing.
- **Git Hash**: msqp.hamsci.org 98e8e69

## [2026-10-29 16:28 CDT]
- **Tool**: Claude (Anthropic), claude-opus-5-5
- **Session Purpose**: Rob Suggs (NN4NT) asked for the second iteration of the underdense-decay analysis, to compare echo decay times across 28, 50 and 144 MHz. The changes: drop the FFT/bandpass filter and use the full-band signal; process band directories named "RXCALL GRID SHOWER MonYY BAND"; and add Rx→Tx distance and bearing, plus shower radiant az/el at the path midpoint, to every echo. The script was then run on the full NN4SA EM64pp Perseids (Aug 2026) dataset for 10 m, 6 m and 2 m.
- **Sections/Files Affected**: `analysis/underdense_decay.py` (rewritten); `requirements.txt` (adds `ephem`).
- **Nature of Contribution**: Code generation and data analysis.
- **Human Review Status**: Partially reviewed. Rob reviewed the 100-file test plots and results and set the analysis rules: keep the 2 s cutoff on all bands, keep the long-τ 2 m echoes, report negative radiant elevations unfiltered, ignore CMSH/TEST and .adi files, and treat "CQ 265" as a QSY request. Full-run outputs are pending review, and the code has not been reviewed line by line.
- **Verification**:
  - The envelope is a full-band running RMS: 2 ms for fitting, 10 ms for detection, 1 ms hop. The impulse blanker is kept.
  - A squared-spectrum MSK144 line test failed to separate echoes from noise and was removed. Each burst must now have a WSJT-X decode within 0.15 s.
  - 2 m echoes show a 30–130 ms flat top, so the fit is a plateau followed by an exponential, with the plateau capped at 150 ms.
  - Full run: 4740 WAVs, 1298 underdense echoes. Median τ: 10 m 295 ms (n=41), 6 m 155 ms (n=1198), 2 m 105 ms (n=59). The 10m/6m ratio is 1.9 and 6m/2m is 1.5, against λ² predictions of 3.2 and 8.2.
  - The first full run accepted 80 artifacts from signals already present when the audio started. A start-of-audio rejection rule was added and the full run repeated, rejecting 449 such signals.
  - 10 echoes lack geometry because the Tx never sent a grid. There are no negative radiant elevations, since the PER radiant is circumpolar at EM64. Four mostly-silent 2 m files were skipped.
  - Data and results stay local, under the gitignored `data/`.
- **Git Hash**: msqp.hamsci.org bf1bf72 (local, not pushed)

## [2026-11-04 11:34 CST]
- **Tool**: Claude (Anthropic), claude-opus-5-5
- **Session Purpose**: Rob Suggs (NN4NT) asked for the work from several sessions (2026-10-30 to 2026-11-04) to be committed to `HamSCI/MSQP` under a new `data_analysis/` folder, organized so that other contributors can add their own analysis projects. Nathaniel Frissell (W2NAF) chose this repository. The work in those sessions:
  - Tools that read `echoes.csv`: `station_map.py`, `coincident_echoes.py` and `plot_tau_by_band.py`.
  - A power e-folding plot (τ/2) added to `underdense_decay.py`.
  - A new real-time underdense meteor counter, `rt_meteor_counter`, which listens to forward scatter of ATSC pilot carriers on TV channels 2–6 and has its own clip-plotting tool.
- **Sections/Files Affected**:
  - New `data_analysis/` with `README.md`, `CLAUDE.md` and `.gitignore`.
  - AI governance files: `.claude/` (settings, `/commit` workflow, `ai-governance.md` rewritten for this repository, `python-code.md`) and `ai/ai_usage_log.md`.
  - `underdense_decay/`: `underdense_decay.py` (power plot; usage lines updated for the new folder), plus `plot_tau_by_band.py`, `station_map.py`, `coincident_echoes.py`, `README.md` and `requirements.txt`.
  - `rt_meteor_counter/`: the `rt_meteor_counter` package, `tools/` (`plot_clip.py`, `make_test_signal.py`, `check_detections.py`), `README.md`, `requirements.txt` and `run_meteor_counter.bat`.
- **Nature of Contribution**: Code generation, data analysis and repository organization.
- **Human Review Status**: Partially reviewed.
  - Rob has reviewed the station maps, the coincident-echo results and the decay-time-by-band plots, and asked for the power plot himself.
  - He ran `rt_meteor_counter` live: an RTL-SDR on channel 3, an afternoon run and an overnight run on 2–3 November 2026. He compared its detections with his own waterfall and ear notes.
  - The code has not been reviewed line by line.
- **Verification**:
  - `rt_meteor_counter` detector thresholds were tuned on synthetic signals (`tools/make_test_signal.py`). A live run found and fixed several problems:
    - an SDR enumeration crash in SoapySDR on Windows;
    - wrong nominal pilot frequencies (corrected to 309.441 kHz above the channel edge);
    - audio dropouts at thresholds below 10 dB (fixed with vectorized grouping and an integrated-SNR pre-screen);
    - failed decay fits (fixed with multi-start fitting).
  - Overnight run of 2–3 November 2026: 23 meteors counted. Of the 11 times Rob noted on the waterfall, 2 were counted and 8 were logged as rejects with narrowband traces that are not exponential decays. The site is noisy, and further testing is planned at a quieter site.
  - A check of the 2 m underdense echoes in the Perseids data found no clipping: the loudest echo peaked 3.5 dB below full scale, and plateau and τ do not depend on echo SNR.
  - After the move, the scripts were run from their new folders: `plot_tau_by_band.py` and `coincident_echoes.py` on a copy of `echoes.csv`, and imports of `station_map.py` and the `rt_meteor_counter` package.
  - No data, results, recordings or plots are committed; `.gitignore` excludes them.
- **Git Hash**: f008193
