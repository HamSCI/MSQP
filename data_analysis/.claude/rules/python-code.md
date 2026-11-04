---
paths:
  - "**/*.py"
  - "pyproject.toml"
  - "requirements.txt"
  - "requirements*.txt"
---

# Python Code Rules
*Delete this file if your project does not include Python code.*

## Code Standards
- Follow existing code structure — do not introduce new abstractions without need
- Maintain a `requirements.txt` (or `pyproject.toml`) and keep it up to date when adding dependencies
- Do not commit credentials, API keys, or sensitive configuration — use environment variables or a `.env` file that is gitignored

## Commit Workflow for Code
- If code lives in a submodule, commit changes in the submodule first, then update the pointer in the main repo
- Use `[AI-assisted]` prefix on AI-assisted commits
- Reference issue trackers (GitHub issues, project boards) in commit messages where applicable (e.g., `closes #N`)
- Ask before pushing to any remote

## Open Source Considerations
- If the code will be released open-source, keep commit history clean and suitable for public visibility
- Document significant design decisions in code comments or in a `docs/` directory
- Apply the project's chosen open-source license consistently (`LICENSE` file at the repo root)
