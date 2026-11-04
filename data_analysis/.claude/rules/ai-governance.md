# AI Governance and Policy Compliance

All AI-assisted work on this project must comply with the following policies. Violations risk project credibility with funders and with academic, scientific, and amateur-radio communities.

## Applicable Policies (Always)

### 1. University of Scranton AI Policy (September 2025)
- Maintain transparency about AI use in all project outputs
- Human oversight and review of all AI-generated content is required
- Do not use AI to misrepresent authorship or intellectual contribution
- Ethical use aligned with University academic integrity standards

### 2. HamSCI Generative AI Use Agreement (January 2026)
- Log the AI tool name, version, and date/time for every substantive session
- Verify all AI-generated outputs before incorporating into project artifacts
- Do not submit confidential, ITAR/EAR-controlled, or proprietary material to AI tools

### 3. NASA Guidance on Generative AI in Funded Research
- Disclose AI-assisted content in deliverables to NASA-funded projects
- Maintain human authorship and accountability for scientific claims
- Do not submit ITAR/EAR-controlled, confidential, or unpublished mission data to AI tools
- Verify factual claims against authoritative sources before publication

### 4. NSF Guidance on Responsible Use of Generative AI in Funded Research
- Disclose AI use in NSF deliverables, proposals, and publications as required
- Maintain human authorship and intellectual responsibility for results
- Do not use AI to generate or substantially shape proposal review content unless explicitly authorized
- Do not submit confidential or unpublished data to AI tools

### 5. Project-Specific Expectations
This code supports the HamSCI Meteor Scatter QSO Party (MSQP) and the HamSCI Meteor Scatter Working Group, and is shared with the HamSCI community through the `HamSCI/MSQP` repository. In addition to the standing policies above:
- Work products released to the HamSCI community follow the HamSCI Generative AI Use Agreement.
- Each project's maintainer reviews AI-generated code and results and is accountable for them; the log records how far that review has gone.
- Scientific results from AI-assisted analysis (decay times, rates, diffusion coefficients) are checked against the data and the literature by a person before they are presented or published, and the AI assistance is disclosed.

## AI Usage Logging Requirements

**Every substantive AI session must be logged in `ai/ai_usage_log.md` before committing.**

Each log entry must include:
- **Date/Time**: From system clock — never estimated (use `date` command)
- **Tool**: Name and version (e.g., "Claude (Anthropic), claude-opus-4-7")
- **Session Purpose**: What you were trying to accomplish
- **Sections/Files Affected**: Which files, sections, or documents were touched
- **Nature of Contribution**: Draft, edit, analysis, code generation, research, etc.
- **Human Review Status**: Reviewed and verified / Partially reviewed / Pending review
- **Git Hash**: Add after committing

Use the `/commit` command to handle logging and committing in the correct order.

## What AI Should NOT Do
- Fabricate or hallucinate citations, references, data, or quotations
- Claim authorship or present AI output as purely human work
- Submit sensitive student data, unpublished data, ITAR/EAR-controlled, or proprietary information to AI tools
- Skip the AI usage log before committing AI-assisted changes
- Force-push or hard-reset without explicit user instruction
