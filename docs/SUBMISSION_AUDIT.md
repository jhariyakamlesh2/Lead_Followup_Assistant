# Submission package audit

Audited project scope: tracked source, configuration, documentation, assets, schema, sample data and tests.

## Included

- [x] Runnable modular Python source
- [x] SQLite schema and relationship definitions
- [x] Synthetic runtime and sample SQLite databases
- [x] Lead, interaction, programme-fact, draft, template and audit entities
- [x] Streamlit CRM-style workflow
- [x] Deterministic NLP cleaning, tokenization, stage, preference and open-question analysis
- [x] Anthropic Claude integration with structured output and provider/model metadata
- [x] Approved-fact grounding and JSON/fact-ID validation
- [x] Human review for draft approval, rejection or revision
- [x] Explicit SMTP send action for approved email drafts
- [x] Prompt pack and prompt-version notes
- [x] Architecture, setup, privacy, demo and test documentation
- [x] 65 automated tests covering normal, validation and failure scenarios
- [x] Duplicate lead, interaction, fact, template, draft and audit cleanup
- [x] Synthetic data and no hard-coded API keys

## External submission items

- [ ] Record and attach the live walkthrough/video
- [ ] Add the final live/deployed URL only if a public deployment is approved
- [ ] Add a repository release/tag or commit before final submission

## Excluded generated files

The following are local/generated and are not source deliverables:

- `.venv/`
- `.venv313/`
- `.pytest_cache/`
- `__pycache__/`
- `.env` secrets

The runtime database under `data/` is local and excluded from Git. The clean sample database under `sample_data/` is the submission fixture.
