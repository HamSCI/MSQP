# /commit — AI-Assisted Commit Workflow

Use this command any time you finish a substantive AI-assisted work session.

This workflow handles flat repos (no submodules), single-submodule repos (e.g., Overleaf only), and multi-submodule repos. Submodules are auto-detected from `git submodule status`.

## Steps

### 1. Get the current timestamp
```bash
date
```
Use this exact output — never estimate the date/time.

### 2. Identify all changes
Check status across the main repo and every submodule:
```bash
git status
git submodule foreach 'git status'
```

Show diff summaries:
```bash
git diff --stat
git submodule foreach 'git diff --stat'
```

If `git submodule foreach` produces no output, the repo has no submodules — proceed without them.

### 3. Ask the user for session purpose
Draft a purpose of this session for the AI log. Show it to the user, and ask them to confirm.

### 4. Draft the AI usage log entry
Use this format. Use the **actual running model ID** in the Tool field (e.g., `claude-opus-4-7`), not a placeholder.

```
## [YYYY-MM-DD HH:MM TZ]
- **Tool**: Claude (Anthropic), <actual-model-id>
- **Session Purpose**: [user's description]
- **Sections/Files Affected**: [list changed files and sections]
- **Nature of Contribution**: [Draft / Edit / Analysis / Code generation / Research / etc.]
- **Human Review Status**: [Reviewed and verified / Partially reviewed / Pending review]
- **Git Hash**: [fill in after committing]
```

Present the draft to the user. Wait for confirmation or corrections.

### 5. Append the entry to `ai/ai_usage_log.md`

### 6. Commit in submodules FIRST (if any have changes)
For each submodule with changes:
```bash
git -C <submodule-path> add <files>
git -C <submodule-path> commit -m "[AI-assisted] <description>"
```

If there are no submodules, or none have changes, skip this step.

### 7. Commit in the main repo
Stage `ai/ai_usage_log.md`, any updated submodule pointers, and any other changed project files:
```bash
git add ai/ai_usage_log.md <other-files-and-submodule-pointers>
git commit -m "[AI-assisted] <description>"
```

### 8. Fill in the git hash(es)
```bash
git log --oneline -1
```
Update the log entry's **Git Hash** field with the main-repo hash and any submodule hashes (e.g., `main=abc1234, overleaf=def5678`).

If updating the hash field requires a follow-up commit, use a non-`[AI-assisted]` commit message such as `Update AI usage log with git hashes`.

### 9. Ask before pushing
Never push without explicit user instruction.

## Notes

- This folder is `data_analysis/` inside the shared `HamSCI/MSQP` repository. Run these steps from `data_analysis/`, and stage only files under it; other contributors' files elsewhere in the repository are not part of this commit. `git status .` limits the status to this folder.
- Pull before committing (`git pull --ff-only`), since other people commit to this repository through the GitHub web interface.

- The `[AI-assisted]` prefix applies only to commits whose content was produced or substantially shaped with AI assistance. Pure human edits (e.g., the user manually fixes a typo or rewords a sentence) should NOT carry the prefix.
- Commit submodules with their own `[AI-assisted]` prefix when their content is AI-assisted, separately from the main-repo pointer-bump commit.
- Use `git add <specific-files>` rather than `git add -A` or `git add .`, to avoid accidentally staging untracked artifacts (build outputs, credentials, large binaries).
