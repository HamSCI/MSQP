# MSQP data analysis

Analysis code for the HamSCI Meteor Scatter QSO Party (MSQP) and related meteor
scatter observations, inside the `HamSCI/MSQP` repository. The rest of that
repository (papers, working group slides, research questions) belongs to the
Meteor Scatter Working Group; change it only when asked.

**Maintainer of the current projects**: Rob Suggs, NN4NT, co-lead of the HamSCI Meteor
Scatter Working Group.

## Layout
- `underdense_decay/`: echo finding and decay-time fitting on WSJT-X MSK144 WAV files,
  plus tools that read its `echoes.csv` (`plot_tau_by_band.py`, `station_map.py`,
  `coincident_echoes.py`). The tools import from `underdense_decay.py`, so they stay in
  the same folder.
- `rt_meteor_counter/`: real-time underdense meteor counter on distant ATSC pilot
  carriers (TV channels 2–6). PyQt5 GUI; sound card, SoapySDR or WAV input.
- One folder per project, each with its own README and `requirements.txt`. Other
  contributors add projects here too.

## Environment
- Python from radioconda (Windows: `%USERPROFILE%\radioconda\python.exe`). It provides
  numpy, scipy, matplotlib, PyQt5, pyqtgraph and SoapySDR.
- On Windows, SoapySDR needs radioconda's `Library\bin` folders on PATH;
  `rt_meteor_counter/run_meteor_counter.bat` sets them.

## Physics conventions
- Fits report the **amplitude** e-folding time τ. Underdense theory and diffusion
  coefficients use the **power** e-folding time τ_P = τ/2, and τ_P ∝ λ²sec²φ/D.
- Not every MSK144 or pilot-carrier signal is a meteor. Sporadic E, tropospheric and
  aircraft scatter, and impulse noise share the band; the echo tests exist to
  reject them.

## Data handling
- No data, results, recordings or plots in git. MSQP recordings are archived on Zenodo;
  each project works in a local `data/` folder (gitignored here).
- Never delete or overwrite a maintainer's own files in `data/` (for example their
  spreadsheets). Overwrite only files the scripts generate.
- Callsigns and grids are public. Emails, street addresses and phone numbers must
  never be committed.

## AI governance
All AI-assisted work follows `.claude/rules/ai-governance.md`. Log every substantive
session in `ai/ai_usage_log.md` before committing; `/commit` does this in the right
order. Commit only files under `data_analysis/`, and ask before pushing.
