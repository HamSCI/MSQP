# MSQP data analysis

Analysis code for HamSCI Meteor Scatter QSO Party (MSQP) and related meteor scatter
observations. Each project has its own folder, with its own README and requirements.

| Folder | What it does | Maintainer |
|---|---|---|
| [`underdense_decay/`](underdense_decay/) | Finds underdense meteor echoes in WSJT-X MSK144 WAV recordings and fits their decay times; tools to map stations, compare bands and plot decay time by band | Rob Suggs, NN4NT |
| [`rt_meteor_counter/`](rt_meteor_counter/) | Real-time underdense meteor counter using forward scatter of distant ATSC TV pilot carriers (sound card or SDR input), with a GUI | Rob Suggs, NN4NT |

## Adding your own project

- Make a new folder here named for what the code does (lowercase, underscores), not
  for who wrote it. Add a row to the table above.
- Give it a `README.md` that says what the code does, how to install what it needs,
  how to run it, and where its input data comes from.
- List its Python packages in its own `requirements.txt`.
- Keep a project's code together. If one script imports another, they belong in the
  same folder.

## Data stays out of this repository

Do not commit recordings, logs, spot files, results or plots. MSQP data is archived
on [Zenodo](https://zenodo.org/communities/hamsci) (see `../Zenodo.md`); a README
should say which Zenodo records a project uses. Each project reads and writes its
data in a local `data/` folder, which `.gitignore` here keeps out of git, along with
WAV files, PNG plots and the real-time counter's output.

Callsigns and grid squares are public by amateur radio convention. Email addresses,
street addresses, phone numbers and other personal details of participants are not,
and must never be committed.

## AI-assisted development

Much of this code was written with Claude Code (Anthropic) and reviewed by its
maintainer. AI use is disclosed and logged:

- [`ai/ai_usage_log.md`](ai/ai_usage_log.md): one entry per substantive AI session.
- [`.claude/`](.claude/): the Claude Code settings, the governance rule
  (`rules/ai-governance.md`), Python conventions and the `/commit` workflow, which
  logs the session before committing.
- [`CLAUDE.md`](CLAUDE.md): project context loaded into each Claude Code session.

To use these, start Claude Code in this `data_analysis` folder, not the repository root.
Contributors who don't use AI tools can ignore them.
